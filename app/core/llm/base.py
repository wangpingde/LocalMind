"""LLM Provider 基类."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Generator

from app.core.llm.reasoning import ChatResult, StreamPart


class LLMProvider(ABC):
    @abstractmethod
    def chat(
        self, messages: list[dict[str, str]], stream: bool = False
    ) -> ChatResult | Generator[StreamPart, None, None]:
        raise NotImplementedError

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError
