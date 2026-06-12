"""Ollama Provider."""

from __future__ import annotations

import json
from collections.abc import Generator

import httpx

from app.core.llm.base import LLMProvider
from app.core.llm.vision_messages import (
    VISION_DESCRIBE_PROMPT,
    encode_image_base64,
    extract_image_base64_from_data_url,
)
from app.core.llm.reasoning import ChatResult, StreamPart, merge_chat_result
from app.storage.lancedb_store import _fallback_embed


class OllamaProvider(LLMProvider):
    def __init__(
        self,
        base_url: str,
        chat_model: str,
        embedding_model: str,
        vision_model: str = "",
        supports_vision: bool | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.vision_model = vision_model.strip() or chat_model
        self._supports_vision = supports_vision
        self.temperature = temperature
        self.max_tokens = max_tokens

    def supports_vision(self) -> bool:
        if self._supports_vision is False:
            return False
        if self._supports_vision is True:
            return True
        if self.vision_model.strip() and self.vision_model != self.chat_model:
            return True
        name = (self.vision_model or self.chat_model).lower()
        return any(
            m in name
            for m in ("vl", "vision", "llava", "moondream", "bakllava", "minicpm-v")
        )

    def vision_explicitly_disabled(self) -> bool:
        return self._supports_vision is False

    def describe_image(self, image_bytes: bytes, mime: str, context: str = "") -> str:
        _, data_url = encode_image_base64(image_bytes, mime=mime)
        prompt = VISION_DESCRIBE_PROMPT.format(context=context or "（无）")
        b64 = extract_image_base64_from_data_url(data_url)
        with httpx.Client(timeout=180.0) as client:
            resp = client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.vision_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "images": [b64],
                    "stream": False,
                    "options": {"temperature": self.temperature, "num_predict": self.max_tokens},
                },
            )
            resp.raise_for_status()
            msg = resp.json().get("message", {})
            return (msg.get("content") or "").strip()

    def chat(
        self, messages: list[dict], stream: bool = False
    ) -> ChatResult | Generator[StreamPart, None, None]:
        if stream:
            return self._stream_chat(messages)
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.chat_model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": self.temperature, "num_predict": self.max_tokens},
                },
            )
            resp.raise_for_status()
            msg = resp.json().get("message", {})
            reasoning = msg.get("thinking") or msg.get("reasoning") or ""
            content = msg.get("content", "")
            return merge_chat_result(content, reasoning)

    def _stream_chat(
        self, messages: list[dict]
    ) -> Generator[StreamPart, None, None]:
        with httpx.Client(timeout=120.0) as client:
            with client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json={
                    "model": self.chat_model,
                    "messages": messages,
                    "stream": True,
                    "options": {"temperature": self.temperature, "num_predict": self.max_tokens},
                },
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    message = data.get("message", {})
                    thinking = message.get("thinking") or message.get("reasoning") or ""
                    if thinking:
                        yield StreamPart(kind="reasoning", text=thinking)
                    content = message.get("content", "")
                    if content:
                        yield StreamPart(kind="content", text=content)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = []
        try:
            with httpx.Client(timeout=60.0) as client:
                for text in texts:
                    resp = client.post(
                        f"{self.base_url}/api/embeddings",
                        json={"model": self.embedding_model, "prompt": text},
                    )
                    resp.raise_for_status()
                    vectors.append(resp.json().get("embedding", []))
            return vectors if vectors else _fallback_embed(texts)
        except Exception:
            return _fallback_embed(texts)
