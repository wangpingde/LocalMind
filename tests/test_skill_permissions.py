"""Skill 权限与工具白名单测试."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config.app_config import AppSettings
from app.core.skills.skill import Skill
from app.core.skills.skill_permissions import allowed_tool_names, is_tool_allowed, scripts_allowed
from app.core.tools.registry import ToolRegistry


@pytest.fixture
def file_organizer_skill() -> Skill:
    root = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "resources"
        / "skill_market"
        / "packages"
        / "file_organizer"
    )
    return Skill.from_directory(root)


def test_allowed_tool_names_whitelist(file_organizer_skill):
    allowed = allowed_tool_names([file_organizer_skill])
    assert allowed is not None
    assert "list_files" in allowed
    assert "run_skill_script" in allowed
    assert "read_skill_asset" in allowed
    assert "read_file" not in allowed


def test_is_tool_allowed_denies_unlisted(file_organizer_skill):
    assert is_tool_allowed("list_files", [file_organizer_skill])
    assert not is_tool_allowed("read_file", [file_organizer_skill])


def test_openai_schemas_for_filters(file_organizer_skill):
    reg = ToolRegistry()
    schemas = reg.openai_schemas_for([file_organizer_skill])
    names = {s["function"]["name"] for s in schemas}
    assert "list_files" in names
    assert "run_skill_script" in names
    assert "read_file" not in names


def test_scripts_allowed_requires_global_shell(file_organizer_skill):
    settings = AppSettings(shell_tool_enabled=False)
    assert not scripts_allowed(file_organizer_skill, settings)
    settings.shell_tool_enabled = True
    assert scripts_allowed(file_organizer_skill, settings)
