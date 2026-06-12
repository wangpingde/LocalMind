"""知识库媒体引用解析."""

from __future__ import annotations

from pathlib import Path

from app.core.rag.media_extractor import IMAGE_SUFFIXES

MEDIA_TAG_PREFIX = "media:"


def format_media_tags(kind: str, ref_path: str, extra: str = "") -> str:
    """构造 chunk tags，如 media:image;ref=inbox/a.png"""
    base = f"{MEDIA_TAG_PREFIX}{kind};ref={ref_path}"
    if extra:
        return f"{base};{extra}"
    return base


def parse_media_ref(tags: str | None) -> str | None:
    if not tags:
        return None
    for part in tags.split(";"):
        part = part.strip()
        if part.startswith("ref="):
            value = part[4:].strip()
            return value or None
    return None


def is_media_chunk(tags: str | None, content: str | None = None) -> bool:
    if tags and MEDIA_TAG_PREFIX in tags:
        return True
    text = content or ""
    return "[图片描述]" in text or "[视频画面]" in text


def resolve_media_absolute(knowledge_dir: Path, ref_or_doc_path: str | None) -> Path | None:
    if not ref_or_doc_path:
        return None
    knowledge = knowledge_dir.resolve()
    candidate = (knowledge / ref_or_doc_path.replace("\\", "/")).resolve()
    try:
        candidate.relative_to(knowledge)
    except ValueError:
        return None
    if candidate.is_file() and candidate.suffix.lower() in IMAGE_SUFFIXES:
        return candidate
    return None


def resolve_chunk_media_path(
    knowledge_dir: Path,
    *,
    tags: str | None,
    document_path: str,
) -> str | None:
    """返回相对 knowledge 根目录的媒体路径（用于展示）."""
    ref = parse_media_ref(tags)
    if ref and resolve_media_absolute(knowledge_dir, ref):
        return ref.replace("\\", "/")
    doc = document_path.replace("\\", "/")
    if Path(doc).suffix.lower() in IMAGE_SUFFIXES and resolve_media_absolute(knowledge_dir, doc):
        return doc
    return None
