"""API Key 安全存储."""

from __future__ import annotations

import keyring
from loguru import logger

SERVICE = "LocalMind"


def save_api_key(provider_name: str, api_key: str) -> None:
    if not api_key or api_key.strip() == "":
        return
    keyring.set_password(SERVICE, f"provider:{provider_name}", api_key.strip())
    logger.debug("已保存 {} 的 API Key", provider_name)


def get_api_key(provider_name: str) -> str:
    value = keyring.get_password(SERVICE, f"provider:{provider_name}")
    return value or ""


def delete_api_key(provider_name: str) -> None:
    try:
        keyring.delete_password(SERVICE, f"provider:{provider_name}")
    except keyring.errors.PasswordDeleteError:
        pass


def mask_api_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "****"
    return api_key[:4] + "****" + api_key[-4:]
