"""LLM Provider 基类."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Generator

from app.core.llm.reasoning import ChatResult, StreamPart


class LLMProvider(ABC):
    @abstractmethod
    def chat(
        self, messages: list[dict], stream: bool = False
    ) -> ChatResult | Generator[StreamPart, None, None]:
        raise NotImplementedError

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def supports_vision(self) -> bool:
        return False

    def vision_explicitly_disabled(self) -> bool:
        return False

    def describe_image(self, image_bytes: bytes, mime: str, context: str = "") -> str:
        raise NotImplementedError("当前 Provider 不支持视觉描述")
