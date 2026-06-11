"""深度思考 / Reasoning 内容解析."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

THINK_TAG_RE = re.compile(r"<\s*think\s*>(.*?)<\s*/\s*think\s*>", re.DOTALL | re.IGNORECASE)


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatResult:
    content: str
    reasoning: str = ""
    tool_calls: list[ToolCall] | None = None


@dataclass
class StreamPart:
    kind: str  # reasoning | content | turn_end | tool_call_meta | tool_call_args
    text: str = ""
    tool_calls: list[ToolCall] | None = None
    tool_index: int | None = None
    tool_name: str = ""


def extract_delta_reasoning(delta: Any) -> str:
    """从流式 delta 对象提取思考内容."""
    for key in ("reasoning_content", "reasoning", "thinking"):
        value = getattr(delta, key, None)
        if value:
            return str(value)
    if hasattr(delta, "model_extra") and delta.model_extra:
        for key in ("reasoning_content", "reasoning", "thinking"):
            if delta.model_extra.get(key):
                return str(delta.model_extra[key])
    return ""


def extract_message_reasoning(message: Any) -> str:
    """从完整 message 对象提取思考内容."""
    for key in ("reasoning_content", "reasoning", "thinking"):
        value = getattr(message, key, None)
        if value:
            return str(value)
    if hasattr(message, "model_extra") and message.model_extra:
        for key in ("reasoning_content", "reasoning", "thinking"):
            if message.model_extra.get(key):
                return str(message.model_extra[key])
    return ""


def split_think_tags(text: str) -> tuple[str, str]:
    """从 ... 标签中拆分思考与正文."""
    if not text:
        return "", ""
    parts = [p.strip() for p in THINK_TAG_RE.findall(text) if p.strip()]
    reasoning = "\n\n".join(parts)
    answer = THINK_TAG_RE.sub("", text).strip()
    return reasoning, answer


def merge_chat_result(content: str, reasoning: str = "") -> ChatResult:
    """合并 API 字段与标签解析结果."""
    tag_reasoning, tag_answer = split_think_tags(content or "")
    merged_reasoning = "\n\n".join(filter(None, [reasoning.strip(), tag_reasoning]))
    final_content = tag_answer if tag_answer else (content or "")
    return ChatResult(content=final_content, reasoning=merged_reasoning)


def serialize_assistant_message(
    content: str,
    reasoning: str = "",
    agent_steps: list[dict] | None = None,
) -> str:
    """持久化助手消息（含思考过程与 Agent 步骤）."""
    if reasoning or agent_steps:
        payload: dict[str, Any] = {"answer": content}
        if reasoning:
            payload["reasoning"] = reasoning
        if agent_steps:
            payload["agent_steps"] = agent_steps
        return json.dumps(payload, ensure_ascii=False)
    return content


def parse_assistant_message(raw: str) -> tuple[str, str, list[dict]]:
    """解析助手消息，返回 (reasoning, answer, agent_steps)."""
    if not raw:
        return "", "", []
    stripped = raw.strip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
            if isinstance(data, dict) and ("answer" in data or "content" in data):
                steps = data.get("agent_steps") or []
                if not isinstance(steps, list):
                    steps = []
                return (
                    data.get("reasoning", "") or "",
                    data.get("answer") or data.get("content") or "",
                    steps,
                )
        except json.JSONDecodeError:
            pass
    reasoning, answer = split_think_tags(raw)
    return reasoning, answer, []
