"""LanceDB 向量存储."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import lancedb
import numpy as np
from loguru import logger

EMBEDDING_DIM = 384


def _fallback_embed(texts: list[str]) -> list[list[float]]:
    """无 embedding API 时的简易向量（基于字符哈希）."""
    vectors = []
    for text in texts:
        vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
        for i, ch in enumerate(text[:2000]):
            vec[i % EMBEDDING_DIM] += ord(ch) / 65536.0
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        vectors.append(vec.tolist())
    return vectors


def _zero_vector() -> list[float]:
    return [0.0] * EMBEDDING_DIM


class LanceDBStore:
    def __init__(self, vector_dir: Path) -> None:
        self.vector_dir = vector_dir
        self.vector_dir.mkdir(parents=True, exist_ok=True)
        self.db = lancedb.connect(str(vector_dir))
        self._ensure_tables()

    def _list_tables(self) -> list[str]:
        return self.db.list_tables()

    def _ensure_tables(self) -> None:
        self._create_table_if_missing(
            "documents_vectors",
            {
                "chunk_id": "__init__",
                "document_id": "",
                "path": "",
                "filename": "",
                "content": "",
                "summary": "",
                "tags": "",
                "page_no": 0,
                "heading_path": "",
                "embedding": _zero_vector(),
                "updated_at": "",
            },
            'chunk_id = "__init__"',
        )
        self._create_table_if_missing(
            "memory_vectors",
            {
                "memory_id": "__init__",
                "type": "",
                "content": "",
                "tags": "",
                "embedding": _zero_vector(),
                "updated_at": "",
            },
            'memory_id = "__init__"',
        )
        self._create_table_if_missing(
            "skill_vectors",
            {
                "skill_id": "__init__",
                "name": "",
                "description": "",
                "capabilities": "",
                "embedding": _zero_vector(),
                "updated_at": "",
            },
            'skill_id = "__init__"',
        )

    def _create_table_if_missing(self, name: str, seed_row: dict, delete_filter: str) -> None:
        if name in self._list_tables():
            return
        try:
            self.db.create_table(name, data=[seed_row])
            self.db.open_table(name).delete(delete_filter)
        except ValueError as e:
            if "already exists" not in str(e):
                raise

    def upsert_document_vectors(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        tbl = self.db.open_table("documents_vectors")
        chunk_ids = [r["chunk_id"] for r in rows]
        for cid in chunk_ids:
            try:
                tbl.delete(f'chunk_id = "{cid}"')
            except Exception:
                pass
        tbl.add(rows)
        logger.debug("写入 {} 条文档向量", len(rows))

    def search_documents(
        self, query_vector: list[float], top_k: int = 8
    ) -> list[dict[str, Any]]:
        tbl = self.db.open_table("documents_vectors")
        try:
            results = (
                tbl.search(query_vector)
                .limit(top_k)
                .to_pandas()
                .to_dict(orient="records")
            )
            return results
        except Exception as e:
            logger.warning("向量检索失败: {}", e)
            return []

    def upsert_memory_vectors(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        tbl = self.db.open_table("memory_vectors")
        for r in rows:
            try:
                tbl.delete(f'memory_id = "{r["memory_id"]}"')
            except Exception:
                pass
        tbl.add(rows)

    def search_memories(
        self, query_vector: list[float], top_k: int = 5
    ) -> list[dict[str, Any]]:
        tbl = self.db.open_table("memory_vectors")
        try:
            return (
                tbl.search(query_vector)
                .limit(top_k)
                .to_pandas()
                .to_dict(orient="records")
            )
        except Exception:
            return []

    def clear_document_vectors(self) -> None:
        if "documents_vectors" in self._list_tables():
            self.db.drop_table("documents_vectors")
        self.db = lancedb.connect(str(self.vector_dir))
        self._ensure_tables()
        logger.info("文档向量索引已清空")

    def delete_document_vectors(self, document_id: str) -> None:
        tbl = self.db.open_table("documents_vectors")
        try:
            tbl.delete(f'document_id = "{document_id}"')
        except Exception:
            pass
