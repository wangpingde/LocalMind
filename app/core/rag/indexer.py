"""文档索引器."""

from __future__ import annotations

import hashlib
import threading
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from app.config.workspace import Workspace
from app.core.llm.model_gateway import ModelGateway
from app.core.rag.chunker import Chunker
from app.core.rag.parser import DocParser
from app.security.audit_logger import AuditLogger
from app.storage.lancedb_store import LanceDBStore
from app.storage.sqlite_store import SQLiteStore


class DocumentIndexer:
    def __init__(
        self,
        workspace: Workspace,
        sqlite: SQLiteStore,
        vector_store: LanceDBStore,
        model_gateway: ModelGateway,
        audit: AuditLogger,
    ) -> None:
        self.workspace = workspace
        self.sqlite = sqlite
        self.vector_store = vector_store
        self.model_gateway = model_gateway
        self.audit = audit
        self.parser = DocParser()
        self.chunker = Chunker()
        self._lock = threading.Lock()

    def index_directory(self, sub_path: str | None = None) -> dict:
        knowledge = self.workspace.knowledge_dir
        target = knowledge / sub_path if sub_path else knowledge
        stats = {"indexed": 0, "failed": 0, "skipped": 0, "removed": 0}

        for file_path in target.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in DocParser.SUPPORTED:
                continue
            try:
                result = self.index_file(file_path)
                if result == "indexed":
                    stats["indexed"] += 1
                elif result == "skipped":
                    stats["skipped"] += 1
            except Exception as e:
                stats["failed"] += 1
                logger.error("索引失败 {}: {}", file_path, e)

        with self._lock:
            stats["removed"] = self._prune_stale_index_unlocked(sub_path)
        return stats

    def prune_stale_index(self, sub_path: str | None = None) -> int:
        """移除磁盘上已不存在文件的索引残留."""
        with self._lock:
            return self._prune_stale_index_unlocked(sub_path)

    def _prune_stale_index_unlocked(self, sub_path: str | None = None) -> int:
        knowledge = self.workspace.knowledge_dir.resolve()
        prefix = (sub_path or "").replace("\\", "/").strip("/")
        removed = 0

        for doc in self.sqlite.list_documents():
            doc_path = doc.path.replace("\\", "/")
            if prefix and not (doc_path == prefix or doc_path.startswith(f"{prefix}/")):
                continue
            full_path = knowledge / doc.path
            if full_path.exists():
                continue
            self._purge_document(doc.id, doc.path, reason="file_missing")
            removed += 1

        if removed:
            logger.info("已清理 {} 条失效索引", removed)
        return removed

    def remove_file(self, file_path: Path) -> bool:
        """文件删除或移出知识库时，清理对应索引."""
        with self._lock:
            return self._remove_file_unlocked(file_path)

    def _remove_file_unlocked(self, file_path: Path) -> bool:
        knowledge = self.workspace.knowledge_dir.resolve()
        p = Path(file_path)
        rel_path: str | None = None

        try:
            rel_path = p.resolve().relative_to(knowledge).as_posix()
        except ValueError:
            pass

        doc = self.sqlite.get_document_by_path(rel_path) if rel_path else None
        if not doc:
            name = p.name
            for candidate in self.sqlite.list_documents():
                if candidate.filename == name or candidate.path.replace("\\", "/").endswith(
                    name
                ):
                    doc = candidate
                    break

        if not doc:
            return False

        self._purge_document(doc.id, doc.path, reason="file_deleted")
        return True

    def _purge_document(self, doc_id: str, path: str, reason: str = "") -> None:
        self.sqlite.delete_document(doc_id)
        self.vector_store.delete_document_vectors(doc_id)
        self.audit.log("document_removed", {"path": path, "document_id": doc_id, "reason": reason})
        logger.info("已移除索引: {} ({})", path, reason)

    def index_file(self, file_path: Path) -> str:
        with self._lock:
            return self._index_file_unlocked(file_path)

    def _index_file_unlocked(self, file_path: Path) -> str:
        file_path = file_path.resolve()
        knowledge = self.workspace.knowledge_dir.resolve()
        try:
            rel_path = file_path.relative_to(knowledge).as_posix()
        except ValueError:
            rel_path = str(file_path).replace("\\", "/")

        sha256 = self._file_hash(file_path)
        existing = self.sqlite.get_document_by_path(rel_path)
        if existing and existing.sha256 == sha256 and existing.status == "indexed":
            return "skipped"

        doc_id = existing.id if existing else None
        doc = self.sqlite.upsert_document(
            id=doc_id,
            path=rel_path,
            filename=file_path.name,
            file_type=file_path.suffix.lower().lstrip("."),
            size=file_path.stat().st_size,
            sha256=sha256,
            status="indexing",
            error_message=None,
        )

        try:
            _, sections = self.parser.parse(file_path)
            chunks = self.chunker.chunk_document(doc.id, sections, file_path.name, rel_path)

            if existing:
                self.sqlite.delete_document_chunks(doc.id)
                self.vector_store.delete_document_vectors(doc.id)

            if not chunks:
                self.sqlite.upsert_document(
                    id=doc.id, status="indexed", indexed_at=datetime.now(timezone.utc).isoformat()
                )
                return "indexed"

            texts = [c["content"] for c in chunks]
            embeddings = self.model_gateway.embed(texts)

            sqlite_chunks = []
            vector_rows = []
            now = datetime.now(timezone.utc).isoformat()

            for chunk, emb in zip(chunks, embeddings):
                sqlite_chunks.append(
                    {
                        "id": chunk["id"],
                        "document_id": doc.id,
                        "chunk_index": chunk["chunk_index"],
                        "content": chunk["content"],
                        "summary": chunk["summary"],
                        "page_no": chunk.get("page_no"),
                        "heading_path": chunk.get("heading_path"),
                        "token_count": chunk["token_count"],
                    }
                )
                vector_rows.append(
                    {
                        "chunk_id": chunk["id"],
                        "document_id": doc.id,
                        "path": rel_path,
                        "filename": file_path.name,
                        "content": chunk["content"],
                        "summary": chunk["summary"],
                        "tags": "",
                        "page_no": chunk.get("page_no") or 0,
                        "heading_path": chunk.get("heading_path") or "",
                        "embedding": emb,
                        "updated_at": now,
                    }
                )

            self.sqlite.add_chunks(sqlite_chunks)
            self.vector_store.upsert_document_vectors(vector_rows)
            self.sqlite.upsert_document(
                id=doc.id, status="indexed", indexed_at=now, error_message=None
            )
            self.audit.log("document_indexed", {"path": rel_path, "chunks": len(chunks)})
            logger.info("已索引: {} ({} chunks)", rel_path, len(chunks))
            return "indexed"

        except Exception as e:
            self.sqlite.upsert_document(id=doc.id, status="failed", error_message=str(e))
            self.audit.log("document_index_failed", {"path": rel_path, "error": str(e)})
            raise

    def delete_document_file(self, document_id: str) -> dict[str, str | bool]:
        """删除知识库文件并清理索引."""
        doc = self.sqlite.get_document(document_id)
        if not doc:
            return {"status": "error", "message": "文档不存在"}

        knowledge = self.workspace.knowledge_dir.resolve()
        full_path = (knowledge / doc.path).resolve()
        try:
            full_path.relative_to(knowledge)
        except ValueError:
            return {"status": "error", "message": "文档路径非法"}

        with self._lock:
            if full_path.exists() and full_path.is_file():
                full_path.unlink()
            self._purge_document(doc.id, doc.path, reason="user_delete")

        return {"status": "ok", "path": doc.path, "document_id": document_id}

    def clear_index(self) -> None:
        with self._lock:
            self.sqlite.clear_all_documents()
            self.vector_store.clear_document_vectors()
            self.audit.log("index_cleared", {})
            logger.info("知识库索引已清空")

    @staticmethod
    def _file_hash(file_path: Path) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for block in iter(lambda: f.read(65536), b""):
                h.update(block)
        return h.hexdigest()
