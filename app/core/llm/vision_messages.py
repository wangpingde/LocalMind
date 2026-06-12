"""视觉模型消息与图片编码工具."""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image

VISION_DESCRIBE_PROMPT = """请分析这张图片，用中文输出结构化描述，便于知识库检索。包含：
1. 画面内容摘要（主体、场景、关系）
2. 图中可见文字（OCR，逐条列出）
3. 若为图表/表格，概括数据要点
4. 与文档上下文的关联（若有）

文档上下文：
{context}

请直接输出描述，不要寒暄。"""

MIME_BY_SUFFIX = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}


def guess_mime(path: Path | str, fallback: str = "image/jpeg") -> str:
    suffix = Path(path).suffix.lower()
    return MIME_BY_SUFFIX.get(suffix, fallback)


def encode_image_base64(
    source: Path | bytes,
    *,
    max_side: int = 1024,
    mime: str | None = None,
) -> tuple[str, str]:
    """压缩图片并返回 (mime, data_url)."""
    if isinstance(source, Path):
        raw = source.read_bytes()
        mime = mime or guess_mime(source)
    else:
        raw = source
        mime = mime or "image/jpeg"

    img = Image.open(io.BytesIO(raw))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    w, h = img.size
    if max(w, h) > max_side:
        scale = max_side / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    out_mime = "image/jpeg" if mime != "image/png" else "image/png"
    fmt = "PNG" if out_mime == "image/png" else "JPEG"
    save_kwargs: dict = {"format": fmt}
    if fmt == "JPEG":
        save_kwargs["quality"] = 85
    img.save(buf, **save_kwargs)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    data_url = f"data:{out_mime};base64,{b64}"
    return out_mime, data_url


def build_vision_user_message(text: str, image_data_urls: list[str]) -> dict:
    """构造 OpenAI 兼容的多模态 user message."""
    parts: list[dict] = [{"type": "text", "text": text}]
    for url in image_data_urls:
        parts.append({"type": "image_url", "image_url": {"url": url}})
    return {"role": "user", "content": parts}


def extract_image_base64_from_data_url(data_url: str) -> str:
    """从 data URL 提取 base64 载荷（供 Ollama images 字段）."""
    if "," in data_url:
        return data_url.split(",", 1)[1]
    return data_url
