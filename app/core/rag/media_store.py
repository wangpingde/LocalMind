"""索引阶段持久化提取的图片，供回答时展示."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from app.core.llm.vision_messages import MIME_BY_SUFFIX
from app.core.rag.media_extractor import IMAGE_SUFFIXES

_EXT_BY_MIME = {v: k for k, v in MIME_BY_SUFFIX.items()}


class MediaStore:
    def __init__(self, knowledge_dir: Path) -> None:
        self.knowledge_dir = knowledge_dir.resolve()
        self.root = self.knowledge_dir / ".localmind" / "media"

    def save_image(self, document_id: str, data: bytes, mime: str) -> str:
        """保存图片，返回相对 knowledge_dir 的路径."""
        if not data:
            raise ValueError("空图片数据")
        ext = _EXT_BY_MIME.get(mime, ".jpg")
        digest = hashlib.sha256(data).hexdigest()[:16]
        folder = self.root / document_id
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{digest}{ext}"
        if not target.exists():
            target.write_bytes(data)
        return target.relative_to(self.knowledge_dir).as_posix()

    def is_standalone_image_doc(self, rel_doc_path: str) -> bool:
        return Path(rel_doc_path).suffix.lower() in IMAGE_SUFFIXES

    def delete_document_assets(self, document_id: str) -> None:
        folder = self.root / document_id
        if folder.exists():
            shutil.rmtree(folder)

    def clear_all(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)
