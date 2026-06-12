"""OpenAI-Compatible Provider."""

from __future__ import annotations

import json as _json
from collections.abc import Generator
from typing import Any

from openai import OpenAI

from app.core.llm.base import LLMProvider
from app.core.llm.vision_messages import (
    VISION_DESCRIBE_PROMPT,
    build_vision_user_message,
    encode_image_base64,
)
from app.core.llm.reasoning import (
    ChatResult,
    StreamPart,
    ToolCall,
    extract_delta_reasoning,
    extract_message_reasoning,
    merge_chat_result,
)
from app.storage.lancedb_store import EMBEDDING_DIM, _fallback_embed


class OpenAICompatibleProvider(LLMProvider):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        chat_model: str,
        embedding_model: str,
        vision_model: str = "",
        supports_vision: bool | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> None:
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.vision_model = vision_model.strip() or chat_model
        self._supports_vision = supports_vision
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.client = OpenAI(base_url=base_url, api_key=api_key or "sk-local")

    def chat(
        self,
        messages: list[dict],
        stream: bool = False,
        tools: list[dict] | None = None,
    ) -> ChatResult | Generator[StreamPart, None, None]:
        if stream:
            if tools:
                return self._stream_chat_with_tools(messages, tools)
            return self._stream_chat(messages)
        model = self._model_for_messages(messages)
        kwargs: dict = {
            "model": model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        resp = self.client.chat.completions.create(**kwargs)  # type: ignore[arg-type]
        message = resp.choices[0].message
        reasoning = extract_message_reasoning(message)
        content = message.content or ""
        tool_calls = _extract_tool_calls(message)
        result = merge_chat_result(content, reasoning)
        result.tool_calls = tool_calls
        return result

    def _stream_chat_with_tools(
        self, messages: list[dict], tools: list[dict]
    ) -> Generator[StreamPart, None, None]:
        stream = self.client.chat.completions.create(
            model=self._model_for_messages(messages),
            messages=messages,  # type: ignore[arg-type]
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            tools=tools,
            tool_choice="auto",
            stream=True,
        )
        tool_acc: dict[int, dict[str, str]] = {}
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            reasoning = extract_delta_reasoning(delta)
            if reasoning:
                yield StreamPart(kind="reasoning", text=reasoning)
            content = delta.content or ""
            if content:
                yield StreamPart(kind="content", text=content)
            raw_calls = getattr(delta, "tool_calls", None)
            if raw_calls:
                for tc in raw_calls:
                    idx = tc.index
                    slot = tool_acc.setdefault(
                        idx, {"id": "", "name": "", "arguments": ""}
                    )
                    if tc.id:
                        slot["id"] = tc.id
                    fn = tc.function
                    if fn:
                        if fn.name and fn.name != slot["name"]:
                            slot["name"] = fn.name
                            yield StreamPart(
                                kind="tool_call_meta",
                                tool_index=idx,
                                tool_name=fn.name,
                            )
                        elif fn.name:
                            slot["name"] = fn.name
                        if fn.arguments:
                            slot["arguments"] += fn.arguments
                            yield StreamPart(
                                kind="tool_call_args",
                                tool_index=idx,
                                text=fn.arguments,
                            )
        yield StreamPart(
            kind="turn_end",
            tool_calls=_parse_accumulated_tool_calls(tool_acc),
        )

    def _model_for_messages(self, messages: list[dict]) -> str:
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "image_url":
                        return self.vision_model
        return self.chat_model

    def _stream_chat(
        self, messages: list[dict]
    ) -> Generator[StreamPart, None, None]:
        stream = self.client.chat.completions.create(
            model=self._model_for_messages(messages),
            messages=messages,  # type: ignore[arg-type]
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            reasoning = extract_delta_reasoning(delta)
            if reasoning:
                yield StreamPart(kind="reasoning", text=reasoning)
            content = delta.content or ""
            if content:
                yield StreamPart(kind="content", text=content)
        yield StreamPart(kind="turn_end")

    def supports_vision(self) -> bool:
        if self._supports_vision is False:
            return False
        if self._supports_vision is True:
            return True
        if self.vision_model.strip():
            return True
        name = (self.chat_model or "").lower()
        markers = (
            "gpt-4o",
            "gpt-4.1",
            "gpt-4-turbo",
            "gpt-4v",
            "vision",
            "vl",
            "gemini",
            "claude-3",
            "claude-4",
            "qwen-vl",
            "qwen2-vl",
            "qwen3-vl",
            "glm-4v",
            "deepseek-vl",
            "doubao-vision",
            "yi-vision",
        )
        return any(m in name for m in markers)

    def vision_explicitly_disabled(self) -> bool:
        return self._supports_vision is False

    def describe_image(self, image_bytes: bytes, mime: str, context: str = "") -> str:
        _, data_url = encode_image_base64(image_bytes, mime=mime)
        prompt = VISION_DESCRIBE_PROMPT.format(context=context or "（无）")
        messages = [build_vision_user_message(prompt, [data_url])]
        model = self.vision_model or self.chat_model
        kwargs: dict = {
            "model": model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        resp = self.client.chat.completions.create(**kwargs)  # type: ignore[arg-type]
        message = resp.choices[0].message
        return (message.content or "").strip()

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            resp = self.client.embeddings.create(model=self.embedding_model, input=texts)
            vectors = [d.embedding for d in resp.data]
            if vectors and len(vectors[0]) != EMBEDDING_DIM:
                return _normalize_dims(vectors)
            return vectors
        except Exception:
            return _fallback_embed(texts)


def _parse_accumulated_tool_calls(
    acc: dict[int, dict[str, str]],
) -> list[ToolCall] | None:
    if not acc:
        return None
    parsed: list[ToolCall] = []
    for idx in sorted(acc.keys()):
        slot = acc[idx]
        if not slot.get("name"):
            continue
        args_raw = slot.get("arguments") or "{}"
        try:
            args = _json.loads(args_raw)
        except _json.JSONDecodeError:
            args = {"raw": args_raw}
        parsed.append(
            ToolCall(
                id=slot.get("id") or f"call_{idx}",
                name=slot["name"],
                arguments=args,
            )
        )
    return parsed or None


def _extract_tool_calls(message: Any) -> list[ToolCall] | None:
    raw_calls = getattr(message, "tool_calls", None)
    if not raw_calls:
        return None
    parsed: list[ToolCall] = []
    for tc in raw_calls:
        fn = tc.function
        args_raw = fn.arguments or "{}"
        try:
            args = _json.loads(args_raw)
        except _json.JSONDecodeError:
            args = {"raw": args_raw}
        parsed.append(ToolCall(id=tc.id, name=fn.name, arguments=args))
    return parsed or None


def _normalize_dims(vectors: list[list[float]]) -> list[list[float]]:
    result = []
    for v in vectors:
        if len(v) >= EMBEDDING_DIM:
            result.append(v[:EMBEDDING_DIM])
        else:
            result.append(v + [0.0] * (EMBEDDING_DIM - len(v)))
    return result
