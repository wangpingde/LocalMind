"""知识库配图 HTML 渲染（Qt QTextEdit 需 base64 内嵌，不支持远程 HTTP 图片）."""

from __future__ import annotations

import base64
import logging
from html import escape
from pathlib import Path
from urllib.parse import quote

from app.core.llm.vision_messages import MIME_BY_SUFFIX, encode_image_base64, guess_mime
from app.core.rag.media_refs import resolve_media_absolute
from app.desktop.theme import BG_CARD, BORDER, DANGER, TEXT_MUTED

logger = logging.getLogger(__name__)


def _bytes_to_data_url(data: bytes, rel_path: str) -> str:
    mime = guess_mime(rel_path)
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def resolve_image_data_url(
    rel_path: str,
    *,
    knowledge_dir: Path | str | None = None,
    api_base_url: str | None = None,
) -> str | None:
    """将知识库相对路径转为可在 QTextEdit 中显示的 data URL."""
    rel = rel_path.replace("\\", "/").strip()
    if not rel:
        return None

    if knowledge_dir:
        resolved = resolve_media_absolute(Path(knowledge_dir), rel)
        if resolved:
            try:
                _, data_url = encode_image_base64(resolved)
                return data_url
            except Exception as e:
                logger.warning("读取本地配图失败 {}: {}", rel, e)

    if api_base_url:
        try:
            import httpx

            url = f"{api_base_url.rstrip('/')}/api/knowledge/media?path={quote(rel)}"
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(url)
                if resp.status_code == 200 and resp.content:
                    return _bytes_to_data_url(resp.content, rel)
        except Exception as e:
            logger.warning("API 拉取配图失败 {}: {}", rel, e)

    return None


def format_citation_images_html(
    images: list[dict],
    *,
    knowledge_dir: Path | str | None = None,
    api_base_url: str = "http://127.0.0.1:17777",
) -> str:
    if not images:
        return ""

    blocks: list[str] = [
        f'<div style="margin-top:12px; padding-top:10px; border-top:1px solid {BORDER};">',
        f'<div style="color:{TEXT_MUTED}; font-size:12px; margin-bottom:8px;">'
        f"引用配图 ({len(images)})</div>",
    ]
    shown = 0
    for img in images:
        path = (img.get("path") or "").replace("\\", "/")
        if not path:
            continue
        data_url = resolve_image_data_url(
            path, knowledge_dir=knowledge_dir, api_base_url=api_base_url
        )
        caption = escape(img.get("heading_path") or img.get("filename") or path)
        if data_url:
            shown += 1
            blocks.append(
                f'<div style="margin-bottom:10px; padding:8px; background:{BG_CARD}; '
                f'border-radius:8px; border:1px solid {BORDER};">'
                f'<img src="{data_url}" style="max-width:100%; max-height:480px; '
                f'border-radius:6px;" />'
                f'<div style="color:{TEXT_MUTED}; font-size:11px; margin-top:6px;">{caption}</div>'
                f"</div>"
            )
        else:
            blocks.append(
                f'<div style="margin-bottom:8px; padding:8px; color:{DANGER}; '
                f'font-size:12px;">配图无法加载: {caption}</div>'
            )

    if shown == 0:
        blocks.append(
            f'<div style="color:{DANGER}; font-size:12px;">配图文件未找到，请重新索引知识库。</div>'
        )
    blocks.append("</div>")
    return "".join(blocks)
