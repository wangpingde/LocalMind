"""Agent 多步执行过程渲染（对话区 ChatGPT 风格）."""

from __future__ import annotations

import html
import json
from typing import Any

from app.desktop.message_renderer import render_message_body

REASONING_COLOR = "#8b7ec8"
TOOL_COLOR = "#6eb5ff"
RESULT_OK = "#5fd4a4"
RESULT_WARN = "#e8b86d"
RESULT_ERR = "#f07178"
TIMELINE_BORDER = "#2a2540"


def _escape(text: str) -> str:
    return html.escape(text).replace("\n", "<br>")


def _format_json_preview(data: Any, limit: int = 600) -> str:
    try:
        text = json.dumps(data, ensure_ascii=False, indent=2)
    except TypeError:
        text = str(data)
    if len(text) > limit:
        text = text[:limit] + "\n..."
    return _escape(text)


def _step_header(step_index: int, title: str, *, color: str) -> str:
    return (
        f'<div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">'
        f'<span style="display:inline-flex; align-items:center; justify-content:center; '
        f'min-width:22px; height:22px; border-radius:11px; background:#1a1a28; '
        f'color:{color}; font-size:11px; font-weight:700;">{step_index}</span>'
        f'<span style="color:{color}; font-size:12px; font-weight:600; '
        f'letter-spacing:0.5px;">{title}</span></div>'
    )


def _step_card(inner: str, *, border_color: str = TIMELINE_BORDER) -> str:
    return (
        f'<div style="margin:0 0 12px 0; padding:12px 14px; background:#0c0c14; '
        f'border-radius:10px; border:1px solid {border_color};">{inner}</div>'
    )


def render_agent_steps_html(
    steps: list[dict[str, Any]],
    *,
    streaming: bool = False,
) -> str:
    """将 agent_steps 渲染为对话区时间线 HTML."""
    display = [s for s in steps if s.get("step_type") != "answer"]
    if not display:
        return ""

    parts = [
        '<div class="agent-timeline" style="margin-bottom:14px;">',
        '<div style="color:#7a7a90; font-size:11px; font-weight:600; '
        'letter-spacing:1px; margin-bottom:10px;">⚙️ 执行过程</div>',
    ]

    last_reasoning_idx = max(
        (i for i, s in enumerate(display) if s.get("step_type") == "reasoning"),
        default=-1,
    )

    step_index = 0
    for i, step in enumerate(display):
        stype = step.get("step_type", "")
        if stype == "reasoning":
            step_index += 1
            text = step.get("text", "").strip()
            if not text:
                continue
            step_streaming = (
                streaming and i == last_reasoning_idx and i == len(display) - 1
            )
            body = render_message_body(
                text, role="reasoning", streaming=step_streaming
            )
            inner = _step_header(step_index, "思考", color=REASONING_COLOR) + body
            parts.append(
                _step_card(
                    inner,
                    border_color="#3d3560",
                )
            )
        elif stype == "tool_call":
            step_index += 1
            tool = step.get("tool", "tool")
            args_stream = step.get("_args_text", "")
            if args_stream and not step.get("arguments"):
                args_preview = _escape(args_stream)
                if streaming and i == len(display) - 1:
                    args_preview += (
                        '<span style="color:#6eb5ff; opacity:0.85; font-weight:300;">▍</span>'
                    )
            else:
                args_preview = _format_json_preview(step.get("arguments", {}))
            inner = (
                _step_header(step_index, f"调用工具 · {tool}", color=TOOL_COLOR)
                + f'<div style="color:#9aa0b8; font-size:12px; margin-bottom:6px;">参数</div>'
                + f'<pre style="margin:0; padding:10px 12px; background:#080810; '
                f'border-radius:8px; border:1px solid #252530; font-size:12px; '
                f'line-height:1.5; white-space:pre-wrap; color:#d8d8e8;">{args_preview}</pre>'
            )
            parts.append(_step_card(inner, border_color="#2a3a4a"))
        elif stype == "tool_result":
            tool = step.get("tool", "tool")
            result = step.get("result", {})
            status = result.get("status", "unknown")
            if status == "ok":
                color, border, label = RESULT_OK, "#2a4a3a", "成功"
            elif status in ("needs_confirmation", "skipped"):
                color, border, label = RESULT_WARN, "#4a4028", status
            else:
                color, border, label = RESULT_ERR, "#4a2a2a", "失败"
            summary = result.get("message") or ""
            if result.get("succeeded") is not None:
                summary = (
                    f"处理 {result.get('succeeded', 0)}/{result.get('total', 0)} 项"
                )
            if result.get("path"):
                summary = (summary + " · " if summary else "") + str(result.get("path"))
            if not summary and isinstance(result, dict):
                summary = _format_json_preview(result, limit=200).replace("<br>", " ")
            inner = (
                f'<div style="display:flex; align-items:center; gap:8px; margin-bottom:6px;">'
                f'<span style="color:{TOOL_COLOR}; font-size:12px; font-weight:600;">'
                f"📋 {tool}</span>"
                f'<span style="color:{color}; font-size:11px; font-weight:600;">{label}</span></div>'
                f'<div style="color:#b8b8c8; font-size:13px; line-height:1.55;">'
                f"{_escape(summary) if summary else '已完成'}</div>"
            )
            parts.append(_step_card(inner, border_color=border))

    if streaming and display:
        last_type = display[-1].get("step_type")
        if last_type in ("tool_call", "tool_result"):
            parts.append(
                '<div style="color:#7a7a90; font-size:12px; padding:4px 0 8px 0;">'
                "⏳ 继续执行中...</div>"
            )

    parts.append("</div>")
    return "".join(parts)
