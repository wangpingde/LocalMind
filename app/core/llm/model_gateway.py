"""统一模型调用网关."""

from __future__ import annotations

from collections.abc import Generator

from app.config.app_config import ConfigManager, ProviderConfig
from app.core.llm.base import LLMProvider
from app.core.llm.ollama_provider import OllamaProvider
from app.core.llm.openai_compatible_provider import OpenAICompatibleProvider
from app.core.llm.reasoning import ChatResult, StreamPart
from app.security.keyring_store import get_api_key


class ModelGateway:
    def __init__(self, config: ConfigManager) -> None:
        self.config = config

    def _build_provider(self, name: str, cfg: ProviderConfig) -> LLMProvider:
        api_key = get_api_key(name)
        if cfg.type == "ollama":
            return OllamaProvider(
                base_url=cfg.base_url,
                chat_model=cfg.chat_model,
                embedding_model=cfg.embedding_model,
                temperature=cfg.temperature,
                max_tokens=cfg.max_tokens,
            )
        return OpenAICompatibleProvider(
            base_url=cfg.base_url,
            api_key=api_key,
            chat_model=cfg.chat_model,
            embedding_model=cfg.embedding_model,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
        )

    def get_provider(self, provider_name: str | None = None) -> tuple[str, LLMProvider]:
        if provider_name:
            providers = self.config.load_providers()
            if provider_name in providers:
                return provider_name, self._build_provider(provider_name, providers[provider_name])
        name, cfg = self.config.get_active_provider()
        return name, self._build_provider(name, cfg)

    def chat(
        self,
        messages: list[dict],
        stream: bool = False,
        provider_name: str | None = None,
        tools: list[dict] | None = None,
    ) -> ChatResult | Generator[StreamPart, None, None]:
        _, provider = self.get_provider(provider_name)
        if tools and hasattr(provider, "chat"):
            return provider.chat(messages, stream=stream, tools=tools)  # type: ignore[call-arg]
        return provider.chat(messages, stream=stream)

    def supports_tools(self, provider_name: str | None = None) -> bool:
        _, provider = self.get_provider(provider_name)
        return provider.__class__.__name__ == "OpenAICompatibleProvider"

    def embed(self, texts: list[str], provider_name: str | None = None) -> list[list[float]]:
        _, provider = self.get_provider(provider_name)
        return provider.embed(texts)
