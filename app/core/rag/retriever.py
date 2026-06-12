"""RAG 检索引擎."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.core.llm.model_gateway import ModelGateway
from app.core.rag.media_refs import resolve_chunk_media_path
from app.core.project.project_manager import ProjectManager
from app.storage.lancedb_store import LanceDBStore
from app.storage.sqlite_store import SQLiteStore


@dataclass
class RetrievalResult:
    chunk_id: str
    document_id: str
    filename: str
    path: str
    content: str
    summary: str
    score: float
    page_no: int | None = None
    heading_path: str = ""
    media_path: str | None = None
    tags: str = ""


@dataclass
class RAGResponse:
    query: str
    results: list[RetrievalResult] = field(default_factory=list)


class RAGEngine:
    def __init__(
        self,
        vector_store: LanceDBStore,
        sqlite: SQLiteStore,
        model_gateway: ModelGateway,
        knowledge_dir=None,
    ) -> None:
        self.vector_store = vector_store
        self.sqlite = sqlite
        self.model_gateway = model_gateway
        self.knowledge_dir = knowledge_dir

    def _indexed_document_ids(self) -> set[str]:
        return {
            doc.id
            for doc in self.sqlite.list_documents()
            if doc.status == "indexed"
        }

    def retrieve(
        self,
        query: str,
        top_k: int = 8,
        path_prefix: str | None = None,
    ) -> RAGResponse:
        indexed_doc_ids = self._indexed_document_ids()
        if not indexed_doc_ids:
            return RAGResponse(query=query, results=[])

        query_vec = self.model_gateway.embed([query])[0]
        vector_hits = self.vector_store.search_documents(query_vec, top_k=top_k * 3)
        keyword_hits = self._keyword_search(
            query, top_k=top_k, path_prefix=path_prefix, indexed_doc_ids=indexed_doc_ids
        )

        merged: dict[str, RetrievalResult] = {}

        for i, hit in enumerate(vector_hits):
            cid = hit.get("chunk_id", "")
            if not cid or cid == "__init__":
                continue
            doc_id = hit.get("document_id", "")
            if not doc_id or doc_id not in indexed_doc_ids:
                continue
            doc_path = hit.get("path", "")
            if path_prefix and not ProjectManager.path_in_scope(doc_path, path_prefix):
                continue
            score = 1.0 - (i * 0.05)
            merged[cid] = RetrievalResult(
                chunk_id=cid,
                document_id=hit.get("document_id", ""),
                filename=hit.get("filename", ""),
                path=hit.get("path", ""),
                content=hit.get("content", ""),
                summary=hit.get("summary", ""),
                score=score,
                page_no=hit.get("page_no"),
                heading_path=hit.get("heading_path", "") or "",
            )

        for hit in keyword_hits:
            if hit.chunk_id not in merged:
                merged[hit.chunk_id] = hit
            else:
                merged[hit.chunk_id].score = min(1.0, merged[hit.chunk_id].score + 0.2)

        results = sorted(merged.values(), key=lambda r: r.score, reverse=True)[:top_k]
        results = [self._attach_media_path(r) for r in results]
        if path_prefix and len(results) < top_k:
            extra = self._keyword_search(
                query,
                top_k=top_k * 2,
                path_prefix=path_prefix,
                indexed_doc_ids=indexed_doc_ids,
            )
            for hit in extra:
                if hit.chunk_id not in merged:
                    merged[hit.chunk_id] = hit
            results = sorted(merged.values(), key=lambda r: r.score, reverse=True)[:top_k]
            results = [self._attach_media_path(r) for r in results]
        return RAGResponse(query=query, results=results)

    def _attach_media_path(self, result: RetrievalResult) -> RetrievalResult:
        if not self.knowledge_dir:
            return result
        chunk = self.sqlite.get_chunk(result.chunk_id)
        tags = chunk.tags if chunk else result.tags
        media_path = resolve_chunk_media_path(
            self.knowledge_dir,
            tags=tags,
            document_path=result.path,
        )
        if media_path:
            result.media_path = media_path
        if chunk and chunk.tags:
            result.tags = chunk.tags
        return result

    def _keyword_search(
        self,
        query: str,
        top_k: int,
        path_prefix: str | None = None,
        indexed_doc_ids: set[str] | None = None,
    ) -> list[RetrievalResult]:
        keywords = [w for w in re.split(r"\s+", query) if len(w) >= 2]
        if not keywords:
            return []

        docs = self.sqlite.list_documents()
        hits: list[RetrievalResult] = []

        with self.sqlite.session() as s:
            from app.storage.sqlite_store import Chunk, select

            for doc in docs:
                if doc.status != "indexed":
                    continue
                if indexed_doc_ids is not None and doc.id not in indexed_doc_ids:
                    continue
                if path_prefix and not ProjectManager.path_in_scope(doc.path, path_prefix):
                    continue
                chunks = list(
                    s.execute(select(Chunk).where(Chunk.document_id == doc.id)).scalars()
                )
                for chunk in chunks:
                    content_lower = chunk.content.lower()
                    match_count = sum(1 for kw in keywords if kw.lower() in content_lower)
                    if match_count > 0:
                        hits.append(
                            RetrievalResult(
                                chunk_id=chunk.id,
                                document_id=doc.id,
                                filename=doc.filename,
                                path=doc.path,
                                content=chunk.content,
                                summary=chunk.summary or chunk.content[:200],
                                score=0.3 + 0.1 * match_count,
                                page_no=chunk.page_no,
                                heading_path=chunk.heading_path or "",
                            )
                        )

        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]

    def to_dict(self, response: RAGResponse) -> dict[str, Any]:
        return {
            "query": response.query,
            "results": [
                {
                    "chunk_id": r.chunk_id,
                    "document_id": r.document_id,
                    "filename": r.filename,
                    "path": r.path,
                    "content": r.content,
                    "summary": r.summary,
                    "score": r.score,
                    "page_no": r.page_no,
                    "heading_path": r.heading_path,
                    "media_path": r.media_path,
                    "tags": r.tags,
                }
                for r in response.results
            ],
        }

    def collect_citation_images(self, results: list[RetrievalResult]) -> list[dict]:
        """去重收集可展示的图片引用."""
        seen: set[str] = set()
        images: list[dict] = []
        for r in results:
            if not r.media_path or r.media_path in seen:
                continue
            seen.add(r.media_path)
            images.append(
                {
                    "path": r.media_path,
                    "filename": r.filename,
                    "heading_path": r.heading_path,
                    "chunk_id": r.chunk_id,
                }
            )
        return images
