"""应用配置读写."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from app.config.workspace import Workspace


class ProviderConfig(BaseModel):
    type: str = "openai_compatible"
    base_url: str = "https://api.openai.com/v1"
    chat_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    temperature: float = 0.7
    max_tokens: int = 4096


class AppSettings(BaseModel):
    workspace_dir: str = ""
    knowledge_dir: str = ""
    memory_dir: str = ""
    skills_dir: str = ""
    output_dir: str = ""
    api_port: int = 17777
    active_provider: str = "default"
    local_only_mode: bool = True
    send_file_path_to_model: bool = False
    send_memory_to_model: bool = True
    auto_memory_enabled: bool = True
    skill_network_enabled: bool = False
    shell_tool_enabled: bool = False
    tools_enabled: bool = True
    agent_max_steps: int = 8
    auto_confirm_file_write: bool = False


class ConfigManager:
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self._settings: AppSettings | None = None
        self._providers: dict[str, ProviderConfig] | None = None

    @property
    def app_yaml_path(self) -> Path:
        return self.workspace.config_dir / "app.yaml"

    @property
    def providers_yaml_path(self) -> Path:
        return self.workspace.config_dir / "model_providers.yaml"

    def load_settings(self) -> AppSettings:
        if self._settings is not None:
            return self._settings
        data: dict[str, Any] = {}
        if self.app_yaml_path.exists():
            data = yaml.safe_load(self.app_yaml_path.read_text(encoding="utf-8")) or {}
        settings = AppSettings(**data)
        if not settings.workspace_dir:
            settings.workspace_dir = str(self.workspace.root)
        if not settings.knowledge_dir:
            settings.knowledge_dir = str(self.workspace.knowledge_dir)
        if not settings.memory_dir:
            settings.memory_dir = str(self.workspace.memory_dir)
        if not settings.skills_dir:
            settings.skills_dir = str(self.workspace.skills_dir)
        if not settings.output_dir:
            settings.output_dir = str(self.workspace.outputs_dir)
        self._settings = settings
        return settings

    def save_settings(self, settings: AppSettings) -> None:
        self.app_yaml_path.write_text(
            yaml.safe_dump(settings.model_dump(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        self._settings = settings

    def load_providers(self) -> dict[str, ProviderConfig]:
        if self._providers is not None:
            return self._providers
        data: dict[str, Any] = {}
        if self.providers_yaml_path.exists():
            data = yaml.safe_load(self.providers_yaml_path.read_text(encoding="utf-8")) or {}
        self._providers = {k: ProviderConfig(**v) for k, v in data.items()}
        return self._providers

    def save_providers(self, providers: dict[str, ProviderConfig]) -> None:
        payload = {k: v.model_dump() for k, v in providers.items()}
        self.providers_yaml_path.write_text(
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        self._providers = providers

    def get_active_provider(self) -> tuple[str, ProviderConfig]:
        settings = self.load_settings()
        providers = self.load_providers()
        name = settings.active_provider
        if name not in providers:
            name = next(iter(providers), "default")
        return name, providers.get(name, ProviderConfig())
