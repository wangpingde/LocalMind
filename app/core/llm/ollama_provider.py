"""Ollama Provider."""

from __future__ import annotations

import json
from collections.abc import Generator

import httpx

from app.core.llm.base import LLMProvider
from app.core.llm.reasoning import ChatResult, StreamPart, merge_chat_result
from app.storage.lancedb_store import _fallback_embed


class OllamaProvider(LLMProvider):
    def __init__(
        self,
        base_url: str,
        chat_model: str,
        embedding_model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.embedding_model = embedding_model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def chat(
        self, messages: list[dict[str, str]], stream: bool = False
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
        self, messages: list[dict[str, str]]
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
