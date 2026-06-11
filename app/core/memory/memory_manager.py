"""长期记忆管理."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.core.llm.model_gateway import ModelGateway
from app.storage.lancedb_store import LanceDBStore
from app.storage.sqlite_store import Memory, SQLiteStore


@dataclass
class MemoryHit:
    id: str
    type: str
    content: str
    score: float
    tags: list[str]


class MemoryManager:
    def __init__(
        self,
        sqlite: SQLiteStore,
        vector_store: LanceDBStore,
        model_gateway: ModelGateway,
    ) -> None:
        self.sqlite = sqlite
        self.vector_store = vector_store
        self.model_gateway = model_gateway

    def search(
        self,
        query: str,
        memory_types: list[str] | None = None,
        project_id: str | None = None,
    ) -> list[MemoryHit]:
        active = self.sqlite.list_memories()
        if memory_types:
            active = [m for m in active if m.type in memory_types and m.status == "active"]
        else:
            active = [m for m in active if m.status == "active"]

        if project_id:
            active = [
                m
                for m in active
                if m.project_id in (None, "", project_id)
            ]

        if not active:
            return []

        query_vec = self.model_gateway.embed([query])[0]
        vector_hits = self.vector_store.search_memories(query_vec, top_k=10)

        hits: dict[str, MemoryHit] = {}
        for i, vh in enumerate(vector_hits):
            mid = vh.get("memory_id", "")
            if not mid:
                continue
            mem = self.sqlite.get_memory(mid)
            if not mem or mem.status != "active":
                continue
            if memory_types and mem.type not in memory_types:
                continue
            score = 1.0 - i * 0.08
            if project_id and mem.project_id == project_id:
                score += 0.15
            hits[mid] = MemoryHit(
                id=mid,
                type=mem.type,
                content=mem.content,
                score=score,
                tags=self._parse_tags(mem.tags),
            )

        keywords = [w for w in re.split(r"\s+", query) if len(w) >= 2]
        for mem in active:
            content_lower = mem.content.lower()
            match = sum(1 for kw in keywords if kw.lower() in content_lower)
            if match > 0:
                score = 0.4 + 0.15 * match
                if mem.id in hits:
                    hits[mem.id].score = max(hits[mem.id].score, score)
                else:
                    hits[mem.id] = MemoryHit(
                        id=mem.id,
                        type=mem.type,
                        content=mem.content,
                        score=score,
                        tags=self._parse_tags(mem.tags),
                    )

        result = sorted(hits.values(), key=lambda h: h.score, reverse=True)[:5]
        for h in result:
            self.sqlite.touch_memory(h.id)
        return result

    def upsert_memory(
        self,
        memory_type: str,
        content: str,
        tags: list[str] | None = None,
        memory_id: str | None = None,
        source: str = "manual",
        confidence: float = 1.0,
        project_id: str | None = None,
    ) -> Memory:
        if memory_id:
            updated = self.sqlite.update_memory(
                memory_id,
                type=memory_type,
                content=content,
                tags=tags,
                status="active",
                confidence=confidence,
                project_id=project_id,
            )
            if updated:
                self._sync_vector(updated)
                return updated

        mem = self.sqlite.create_memory(
            memory_type,
            content,
            tags,
            source=source,
            confidence=confidence,
            project_id=project_id,
        )
        self._sync_vector(mem)
        return mem

    def find_similar(self, content: str, threshold: float = 0.75) -> Memory | None:
        content_lower = content.lower().strip()
        if not content_lower:
            return None

        for mem in self.sqlite.list_memories():
            if mem.status != "active":
                continue
            existing_lower = mem.content.lower().strip()
            if self._text_similarity(content_lower, existing_lower) >= threshold:
                return mem
        return None

    @staticmethod
    def _text_similarity(a: str, b: str) -> float:
        if a in b or b in a:
            return 1.0

        words_a = {w for w in re.split(r"[\s\W]+", a) if len(w) >= 2}
        words_b = {w for w in re.split(r"[\s\W]+", b) if len(w) >= 2}
        if words_a and words_b:
            word_overlap = len(words_a & words_b) / min(len(words_a), len(words_b))
            if word_overlap > 0:
                return word_overlap

        bigrams_a = {a[i : i + 2] for i in range(len(a) - 1)}
        bigrams_b = {b[i : i + 2] for i in range(len(b) - 1)}
        if not bigrams_a or not bigrams_b:
            return 0.0
        return len(bigrams_a & bigrams_b) / min(len(bigrams_a), len(bigrams_b))

    def delete_memory(self, memory_id: str) -> bool:
        return self.sqlite.delete_memory(memory_id)

    def list_all(
        self, memory_type: str | None = None, keyword: str | None = None
    ) -> list[Memory]:
        return self.sqlite.list_memories(memory_type=memory_type, keyword=keyword)

    def disable_memory(self, memory_id: str) -> Memory | None:
        return self.sqlite.update_memory(memory_id, status="disabled")

    def _sync_vector(self, mem: Memory) -> None:
        vec = self.model_gateway.embed([mem.content])[0]
        now = datetime.now(timezone.utc).isoformat()
        self.vector_store.upsert_memory_vectors(
            [
                {
                    "memory_id": mem.id,
                    "type": mem.type,
                    "content": mem.content,
                    "tags": mem.tags or "[]",
                    "embedding": vec,
                    "updated_at": now,
                }
            ]
        )

    @staticmethod
    def _parse_tags(tags_json: str | None) -> list[str]:
        if not tags_json:
            return []
        try:
            return json.loads(tags_json)
        except json.JSONDecodeError:
            return []

    def memory_to_dict(self, mem: Memory) -> dict[str, Any]:
        return {
            "id": mem.id,
            "type": mem.type,
            "content": mem.content,
            "source": mem.source,
            "confidence": mem.confidence,
            "status": mem.status,
            "version": mem.version,
            "created_at": mem.created_at,
            "updated_at": mem.updated_at,
            "last_used_at": mem.last_used_at,
            "tags": self._parse_tags(mem.tags),
            "project_id": mem.project_id,
        }
