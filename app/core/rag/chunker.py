"""文档切块."""

from __future__ import annotations

import re
import uuid
from typing import Any


def _finalize_tags(section: dict) -> str:
    tags = (section.get("tags") or "").strip()
    media_ref = section.get("media_ref")
    if media_ref and "ref=" not in tags:
        extra = f"ref={media_ref}"
        return f"{tags};{extra}" if tags else extra
    return tags


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class Chunker:
    def __init__(
        self,
        chunk_size: int = 800,
        chunk_overlap: int = 120,
        min_chunk_size: int = 100,
        max_chunk_size: int = 1200,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size

    def chunk_document(
        self,
        document_id: str,
        sections: list[dict],
        filename: str,
        rel_path: str,
    ) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        index = 0

        for section in sections:
            text = section.get("content", "").strip()
            if not text:
                continue
            parts = self._split_text(text)
            for part in parts:
                chunk_id = f"chunk_{uuid.uuid4().hex[:12]}"
                chunks.append(
                    {
                        "id": chunk_id,
                        "document_id": document_id,
                        "chunk_index": index,
                        "content": part,
                        "summary": part[:200],
                        "page_no": section.get("page_no"),
                        "heading_path": section.get("heading_path") or "",
                        "tags": _finalize_tags(section),
                        "token_count": estimate_tokens(part),
                        "filename": filename,
                        "path": rel_path,
                    }
                )
                index += 1

        return chunks

    def _split_text(self, text: str) -> list[str]:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        if not paragraphs:
            return [text] if text else []

        parts: list[str] = []
        current = ""

        for para in paragraphs:
            candidate = f"{current}\n\n{para}".strip() if current else para
            tokens = estimate_tokens(candidate)

            if tokens > self.max_chunk_size:
                if current:
                    parts.append(current)
                sub_parts = self._hard_split(para)
                parts.extend(sub_parts)
                current = ""
            elif tokens > self.chunk_size:
                if current:
                    parts.append(current)
                parts.append(para)
                current = ""
            else:
                current = candidate

        if current:
            parts.append(current)

        return self._apply_overlap(parts)

    def _hard_split(self, text: str) -> list[str]:
        words = text.split()
        parts: list[str] = []
        current: list[str] = []
        for w in words:
            current.append(w)
            if estimate_tokens(" ".join(current)) >= self.chunk_size:
                parts.append(" ".join(current))
                current = []
        if current:
            parts.append(" ".join(current))
        return parts or [text]

    def _apply_overlap(self, parts: list[str]) -> list[str]:
        if len(parts) <= 1 or self.chunk_overlap <= 0:
            return parts
        result = [parts[0]]
        for i in range(1, len(parts)):
            prev = parts[i - 1]
            overlap_chars = self.chunk_overlap * 4
            prefix = prev[-overlap_chars:] if len(prev) > overlap_chars else prev
            result.append(f"{prefix}\n\n{parts[i]}")
        return result
