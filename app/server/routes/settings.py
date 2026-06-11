"""设置路由."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config.app_config import AppSettings, ProviderConfig
from app.security.keyring_store import get_api_key, mask_api_key, save_api_key
from app.services import get_services

router = APIRouter(tags=["settings"])


class SettingsUpdate(BaseModel):
    workspace_dir: str | None = None
    knowledge_dir: str | None = None
    memory_dir: str | None = None
    skills_dir: str | None = None
    output_dir: str | None = None
    api_port: int | None = None
    active_provider: str | None = None
    local_only_mode: bool | None = None
    send_file_path_to_model: bool | None = None
    send_memory_to_model: bool | None = None
    auto_memory_enabled: bool | None = None
    skill_network_enabled: bool | None = None
    shell_tool_enabled: bool | None = None
    tools_enabled: bool | None = None
    agent_max_steps: int | None = None
    auto_confirm_file_write: bool | None = None


class ProviderUpdate(BaseModel):
    type: str = "openai_compatible"
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    chat_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    temperature: float = 0.7
    max_tokens: int = 4096


class ProvidersPayload(BaseModel):
    providers: dict[str, ProviderUpdate] = Field(default_factory=dict)
    active_provider: str = "default"


@router.get("/settings")
def get_settings():
    svc = get_services()
    settings = svc.config.load_settings()
    providers = svc.config.load_providers()
    return {
        "settings": settings.model_dump(),
        "providers": {
            name: {
                **cfg.model_dump(),
                "api_key_masked": mask_api_key(get_api_key(name)),
                "has_api_key": bool(get_api_key(name)),
            }
            for name, cfg in providers.items()
        },
        "active_provider": settings.active_provider,
    }


@router.put("/settings")
def save_settings(payload: SettingsUpdate):
    svc = get_services()
    current = svc.config.load_settings()
    data = current.model_dump()
    for k, v in payload.model_dump(exclude_none=True).items():
        data[k] = v
    updated = AppSettings(**data)
    svc.config.save_settings(updated)
    return {"status": "ok", "settings": updated.model_dump()}


@router.put("/settings/providers")
def save_providers(payload: ProvidersPayload):
    svc = get_services()
    providers: dict[str, ProviderConfig] = {}
    for name, p in payload.providers.items():
        if p.api_key:
            save_api_key(name, p.api_key)
        providers[name] = ProviderConfig(
            type=p.type,
            base_url=p.base_url,
            chat_model=p.chat_model,
            embedding_model=p.embedding_model,
            temperature=p.temperature,
            max_tokens=p.max_tokens,
        )
    svc.config.save_providers(providers)
    settings = svc.config.load_settings()
    settings.active_provider = payload.active_provider
    svc.config.save_settings(settings)
    return {"status": "ok"}
