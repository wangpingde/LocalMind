"""Skill 权限与工具白名单."""

from __future__ import annotations

from typing import Any

from app.config.app_config import AppSettings
from app.core.skills.skill import Skill

SKILL_META_TOOLS = frozenset(
    {"run_skill_script", "read_skill_asset", "list_skill_resources"}
)


def scripts_allowed(skill: Skill, settings: AppSettings) -> bool:
    if not settings.shell_tool_enabled:
        return False
    perms = skill.permissions or {}
    if _flag_enabled(perms.get("scripts")):
        return True
    return _flag_enabled(perms.get("shell"))


def allowed_tool_names(skills: list[Skill]) -> set[str] | None:
    """返回 None 表示不限制（使用全部内置工具）."""
    if not skills:
        return None

    tool_sets: list[set[str]] = []
    for skill in skills:
        tools = skill.permissions.get("tools")
        if isinstance(tools, list) and tools:
            tool_sets.append({str(t) for t in tools if t})

    if not tool_sets:
        base: set[str] | None = None
    else:
        base = set()
        for ts in tool_sets:
            base |= ts

    extra = set(SKILL_META_TOOLS)
    for skill in skills:
        if skill.package.has_scripts:
            extra.add("run_skill_script")
        if skill.package.has_assets:
            extra.add("read_skill_asset")
        if skill.package.agents or skill.package.has_scripts or skill.package.has_assets:
            extra.add("list_skill_resources")

    if base is None:
        return None
    return base | extra


def is_tool_allowed(tool_name: str, skills: list[Skill]) -> bool:
    allowed = allowed_tool_names(skills)
    if allowed is None:
        return True
    return tool_name in allowed


def _flag_enabled(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, dict):
        return bool(value.get("enabled", False))
    return False
