"""聊天消息富文本渲染（Markdown / JSON / 代码）."""

from __future__ import annotations

import html
import json
import re

import markdown

from app.desktop.theme import (
    ACCENT,
    AGENT_MSG,
    BG_CARD,
    BG_DEEP,
    BG_ELEVATED,
    DANGER,
    REASONING_MSG,
    TEXT_MUTED,
    USER_MSG,
)

_MD_EXTENSIONS = ["fenced_code", "tables", "nl2br", "sane_lists"]

_CONTENT_BASE = (
    "font-size:14px; line-height:1.75; word-wrap:break-word; overflow-wrap:break-word;"
)

_PRE_STYLE = (
    f"background:{BG_DEEP}; color:#e8e8f0; padding:14px 16px; border-radius:10px; "
    f"border:1px solid #2a2a38; font-family:'Cascadia Code','Consolas','Microsoft YaHei UI',monospace; "
    f"font-size:13px; line-height:1.55; white-space:pre-wrap; margin:8px 0; display:block;"
)

_INLINE_CODE_STYLE = (
    f"background:{BG_ELEVATED}; color:{ACCENT}; padding:2px 6px; border-radius:4px; "
    f"font-family:'Cascadia Code','Consolas',monospace; font-size:12px;"
)


def _escape_for_pre(text: str) -> str:
    """QTextEdit 的 <pre> 不会解析 &quot;，只转义会破坏 HTML 的字符。"""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _has_markdown(text: str) -> bool:
    patterns = (
        r"```",
        r"^#{1,6}\s",
        r"^\s*[-*+]\s",
        r"^\s*\d+\.\s",
        r"\*\*.+\*\*",
        r"__.+__",
        r"^\|.+\|",
        r"^>\s",
        r"`[^`]+`",
    )
    return any(re.search(p, text, re.MULTILINE) for p in patterns)


def _looks_like_json(text: str) -> bool:
    stripped = text.strip()
    if not stripped or stripped[0] not in "{[":
        return False
    try:
        json.loads(stripped)
        return True
    except json.JSONDecodeError:
        return False


def _format_json(text: str) -> str:
    data = json.loads(text.strip())
    return json.dumps(data, ensure_ascii=False, indent=2)


def _markdown_to_html(text: str, *, text_color: str = AGENT_MSG) -> str:
    md = markdown.Markdown(extensions=_MD_EXTENSIONS)
    try:
        body = md.convert(text)
    except Exception:
        return html.escape(text).replace("\n", "<br>")
    return _style_markdown_html(body, text_color=text_color)


def _style_code_fence(match: re.Match[str]) -> str:
    lang = (match.group(1) or "code").strip() or "code"
    code = _escape_for_pre(html.unescape(match.group(2)))
    label = html.escape(lang)
    return (
        f'<div style="margin:10px 0; border-radius:10px; overflow:hidden; border:1px solid #2a2a38;">'
        f'<div style="background:#1a1a24; color:{TEXT_MUTED}; font-size:11px; padding:6px 12px; '
        f'font-family:monospace; border-bottom:1px solid #2a2a38;">{label}</div>'
        f'<pre style="{_PRE_STYLE} margin:0; border:none; border-radius:0;">{code}</pre></div>'
    )


def _style_markdown_html(body: str, *, text_color: str = AGENT_MSG) -> str:
    body = re.sub(
        r'<pre><code(?: class="language-(\w+)")?>([\s\S]*?)</code></pre>',
        _style_code_fence,
        body,
    )
    body = body.replace("<pre>", f'<pre style="{_PRE_STYLE}">')
    body = re.sub(
        r"<code(?![^>]*style=)",
        f'<code style="{_INLINE_CODE_STYLE}"',
        body,
    )
    body = body.replace(
        "<table>",
        '<table style="border-collapse:collapse; width:100%; margin:10px 0; font-size:13px;">',
    )
    body = body.replace(
        "<th>",
        '<th style="border:1px solid #2a2a38; padding:8px 10px; background:#1a1a24; text-align:left;">',
    )
    body = body.replace(
        "<td>",
        '<td style="border:1px solid #2a2a38; padding:8px 10px;">',
    )
    body = re.sub(
        r"<h([1-6])>",
        rf'<h\1 style="color:{text_color}; margin:14px 0 8px 0; font-weight:600;">',
        body,
    )
    body = body.replace(
        "<blockquote>",
        f'<blockquote style="border-left:3px solid {ACCENT}; margin:8px 0; padding:4px 12px; color:{TEXT_MUTED};">',
    )
    body = re.sub(
        r"<a href=",
        f'<a style="color:{ACCENT}; text-decoration:none;" href=',
        body,
    )
    return body


def _wrap_content(inner: str, *, color: str = AGENT_MSG, extra_style: str = "") -> str:
    return (
        f'<div class="chat-content" style="color:{color}; {_CONTENT_BASE} {extra_style}">'
        f"{inner}</div>"
    )


def _streaming_cursor(*, color: str) -> str:
    return (
        f'<span style="color:{color}; opacity:0.85; font-weight:300;">▍</span>'
    )


def _has_unclosed_fence(text: str) -> bool:
    return text.count("```") % 2 == 1


def render_message_body(
    text: str,
    *,
    role: str = "assistant",
    is_error: bool = False,
    streaming: bool = False,
) -> str:
    """将消息正文转为可嵌入 QTextEdit 的 HTML."""
    if not text or not text.strip():
        return ""

    if is_error:
        safe = html.escape(text).replace("\n", "<br>")
        return _wrap_content(safe, color=DANGER)

    stripped = text.strip()
    if role == "user":
        color = USER_MSG
    elif role == "reasoning":
        color = REASONING_MSG
    else:
        color = AGENT_MSG

    extra = ""
    if role == "reasoning":
        extra = "font-style:italic; opacity:0.95;"

    if streaming and _has_unclosed_fence(text):
        safe = html.escape(text).replace("\n", "<br>")
        inner = safe + (_streaming_cursor(color=color) if streaming else "")
        return _wrap_content(inner, color=color, extra_style=extra)

    if _looks_like_json(stripped):
        formatted = _escape_for_pre(_format_json(stripped))
        inner = f'<pre style="{_PRE_STYLE}">{formatted}</pre>'
        if streaming:
            inner += _streaming_cursor(color=color)
        return _wrap_content(inner, color=color, extra_style=extra)

    if role in ("assistant", "reasoning") or _has_markdown(stripped):
        inner = _markdown_to_html(text, text_color=color)
        if streaming:
            inner += _streaming_cursor(color=color)
        return _wrap_content(inner, color=color, extra_style=extra)

    safe = html.escape(text).replace("\n", "<br>")
    if streaming:
        safe += _streaming_cursor(color=color)
    return _wrap_content(safe, color=color, extra_style=extra)
