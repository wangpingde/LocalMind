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
from app.core.rag.index_progress import begin as progress_begin
from app.core.rag.index_progress import finish as progress_finish
from app.core.rag.index_progress import step as progress_step
from app.core.rag.media_extractor import IMAGE_SUFFIXES, VIDEO_SUFFIXES, MediaExtractor
from app.core.rag.media_store import MediaStore
from app.core.rag.multimodal_processor import MultimodalProcessor
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

    def index_directory(self, sub_path: str | None = None, *, force: bool = False) -> dict:
        knowledge = self.workspace.knowledge_dir
        target = knowledge / sub_path if sub_path else knowledge
        stats = {"indexed": 0, "failed": 0, "skipped": 0, "removed": 0}

        progress_begin("reindex", message="正在扫描知识库文件...")
        try:
            files = [
                file_path
                for file_path in target.rglob("*")
                if file_path.is_file()
                and file_path.suffix.lower() in DocParser.SUPPORTED
            ]
            total = len(files)
            progress_begin("reindex", total=total, message="准备重建索引...")

            for i, file_path in enumerate(files, start=1):
                progress_step(
                    current=i,
                    message=f"正在索引 ({i}/{total}): {file_path.name}",
                )
                try:
                    result = self.index_file(file_path, force=force)
                    if result == "indexed":
                        stats["indexed"] += 1
                    elif result == "skipped":
                        stats["skipped"] += 1
                except Exception as e:
                    stats["failed"] += 1
                    logger.error("索引失败 {}: {}", file_path, e)

            progress_step(message="正在清理失效索引...")
            with self._lock:
                stats["removed"] = self._prune_stale_index_unlocked(sub_path)
        finally:
            progress_finish()
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

    def purge_document_index(self, document_id: str, *, reason: str = "manual") -> dict[str, str | int]:
        """清除文档对应的 SQLite 切块、向量索引与媒体缓存."""
        with self._lock:
            return self._purge_document_index_unlocked(document_id, reason=reason)

    def _purge_document_index_unlocked(
        self, document_id: str, *, reason: str = "manual"
    ) -> dict[str, str | int]:
        doc = self.sqlite.get_document(document_id)
        if not doc:
            return {"status": "error", "message": "文档不存在"}
        chunk_count = len(self.sqlite.list_chunk_ids(document_id))
        removed_vectors = self._purge_document(doc.id, doc.path, reason=reason)
        return {
            "status": "ok",
            "document_id": document_id,
            "path": doc.path,
            "chunks_removed": chunk_count,
            "vectors_removed": removed_vectors,
        }

    def _purge_document(self, doc_id: str, path: str, reason: str = "") -> int:
        chunk_ids = self.sqlite.list_chunk_ids(doc_id)
        removed_vectors = self.vector_store.delete_document_vectors(
            doc_id, chunk_ids=chunk_ids
        )
        self._cleanup_media_assets(doc_id)
        self.sqlite.delete_document(doc_id)
        self.audit.log(
            "document_removed",
            {
                "path": path,
                "document_id": doc_id,
                "reason": reason,
                "vectors_removed": removed_vectors,
            },
        )
        logger.info("已移除索引: {} ({}, {} 条向量)", path, reason, removed_vectors)
        return removed_vectors

    def _cleanup_media_assets(self, document_id: str) -> None:
        MediaStore(self.workspace.knowledge_dir).delete_document_assets(document_id)

    def index_file(self, file_path: Path, *, force: bool = False) -> str:
        with self._lock:
            return self._index_file_unlocked(file_path, force=force)

    def _index_file_unlocked(self, file_path: Path, *, force: bool = False) -> str:
        file_path = file_path.resolve()
        knowledge = self.workspace.knowledge_dir.resolve()
        try:
            rel_path = file_path.relative_to(knowledge).as_posix()
        except ValueError:
            rel_path = str(file_path).replace("\\", "/")

        sha256 = self._file_hash(file_path)
        existing = self.sqlite.get_document_by_path(rel_path)
        if (
            not force
            and existing
            and existing.sha256 == sha256
            and existing.status == "indexed"
        ):
            if not self._needs_reindex_media(existing.id, file_path):
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
            sections = self._enrich_with_multimodal(file_path, rel_path, sections, doc.id)
            chunks = self.chunker.chunk_document(doc.id, sections, file_path.name, rel_path)

            if existing:
                old_chunk_ids = self.sqlite.list_chunk_ids(doc.id)
                self.sqlite.delete_document_chunks(doc.id)
                self.vector_store.delete_document_vectors(doc.id, chunk_ids=old_chunk_ids)

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
                        "tags": chunk.get("tags") or "",
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
                        "tags": chunk.get("tags") or "",
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

    def delete_document_file(self, document_id: str) -> dict[str, str | bool | int]:
        """删除知识库文件并清理对应索引."""
        doc = self.sqlite.get_document(document_id)
        if not doc:
            return {"status": "error", "message": "文档不存在"}

        knowledge = self.workspace.knowledge_dir.resolve()
        full_path = (knowledge / doc.path).resolve()
        try:
            full_path.relative_to(knowledge)
        except ValueError:
            return {"status": "error", "message": "文档路径非法"}

        file_deleted = False
        progress_begin("delete", message=f"正在删除: {doc.filename}")
        try:
            with self._lock:
                if full_path.exists() and full_path.is_file():
                    try:
                        full_path.unlink()
                        file_deleted = True
                    except OSError as e:
                        logger.warning("删除磁盘文件失败 {}: {}", full_path, e)
                progress_step(message="正在清理索引与向量...")
                purge = self._purge_document_index_unlocked(document_id, reason="user_delete")
                if purge.get("status") != "ok":
                    return purge
        finally:
            progress_finish()

        return {
            "status": "ok",
            "path": doc.path,
            "document_id": document_id,
            "file_deleted": file_deleted,
            "chunks_removed": purge.get("chunks_removed", 0),
            "vectors_removed": purge.get("vectors_removed", 0),
        }

    def clear_index(self) -> None:
        progress_begin("clear", message="正在清空索引...")
        try:
            with self._lock:
                progress_step(message="正在删除切块记录...")
                self.sqlite.clear_all_documents()
                progress_step(message="正在清空向量索引...")
                self.vector_store.clear_document_vectors()
                progress_step(message="正在清理媒体缓存...")
                MediaStore(self.workspace.knowledge_dir).clear_all()
                self.audit.log("index_cleared", {})
                logger.info("知识库索引与向量数据已清空")
        finally:
            progress_finish()

    def _needs_reindex_media(self, document_id: str, file_path: Path) -> bool:
        """媒体文件缺少有效视觉描述时需重新处理."""
        suffix = file_path.suffix.lower()
        if suffix in IMAGE_SUFFIXES | VIDEO_SUFFIXES:
            return not self.sqlite.document_has_media_description(document_id)
        if self.sqlite.count_document_chunks(document_id) == 0:
            return True
        return False

    def _enrich_with_multimodal(
        self, file_path: Path, rel_path: str, sections: list[dict], document_id: str
    ) -> list[dict]:
        settings = self.model_gateway.config.load_settings()
        if not settings.multimodal_index_enabled:
            return sections

        extractor = MediaExtractor(
            self.workspace.knowledge_dir,
            video_max_frames=settings.video_max_frames,
            video_frame_interval_sec=settings.video_frame_interval_sec,
        )
        assets = extractor.extract(file_path, sections, rel_path=rel_path)
        if not assets:
            return sections

        processor = MultimodalProcessor(
            self.model_gateway,
            self.audit,
            knowledge_dir=self.workspace.knowledge_dir,
            max_images=settings.max_images_per_document,
        )
        media_sections = processor.describe_all(
            assets,
            document_id=document_id,
            document_path=rel_path,
        )
        return self._merge_sections(sections, media_sections)

    @staticmethod
    def _merge_sections(text_sections: list[dict], media_sections: list[dict]) -> list[dict]:
        merged = [s for s in text_sections if (s.get("content") or "").strip()]
        merged.extend(media_sections)
        return merged

    @staticmethod
    def _file_hash(file_path: Path) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for block in iter(lambda: f.read(65536), b""):
                h.update(block)
        return h.hexdigest()
