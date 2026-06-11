"""Skill 展示格式化测试."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.config.app_config import AppSettings
from app.core.skills.skill import Skill
from app.core.skills.skill_presenter import (
    enrich_skill_dict,
    format_package_badge,
    format_used_skills_context,
)

os.environ.setdefault("LOCALMIND_DATA_DIR", str(Path(__file__).resolve().parent.parent / ".dev-data"))


@pytest.fixture
def svc():
    from app.services import init_services

    return init_services()


def _meeting_notes() -> Skill:
    root = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "resources"
        / "skill_market"
        / "packages"
        / "meeting_notes"
    )
    return Skill.from_directory(root)


def test_meeting_notes_package_complete():
    skill = _meeting_notes()
    pkg = skill.package
    assert any(a.name == "minutes_drafter" for a in pkg.agents)
    assert any(s.filename == "format_minutes.py" for s in pkg.scripts)
    assert any(a.rel_path == "minutes_template.md" for a in pkg.assets)
    assert pkg.references_text


def test_format_used_skills_context_with_tool_calls():
    skill = _meeting_notes().to_dict()
    text = format_used_skills_context(
        [skill],
        agent_steps=[
            {
                "step_type": "tool_call",
                "tool": "read_skill_asset",
                "arguments": {"skill_id": "meeting_notes", "path": "minutes_template.md"},
            },
            {
                "step_type": "tool_call",
                "tool": "run_skill_script",
                "arguments": {"skill_id": "meeting_notes", "script": "format_minutes.py"},
            },
        ],
    )
    assert "meeting_notes" in text
    assert "minutes_drafter" in text
    assert "format_minutes.py" in text
    assert "minutes_template.md" in text
    assert "read_skill_asset" in text
    assert "run_skill_script" in text


def test_enrich_skill_dict(svc):
    skill = _meeting_notes()
    settings = AppSettings(shell_tool_enabled=True)
    data = enrich_skill_dict(skill, svc.permission_checker, settings)
    assert data["package"]["agents_count"] >= 1
    assert data["allowed"] is True
    assert isinstance(data["permission_summary"], list)
    assert "Skill 脚本执行" in "; ".join(data["permission_summary"])
    assert format_package_badge(data["package"])
