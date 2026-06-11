"""meeting_notes Skill 工具端到端测试."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("LOCALMIND_DATA_DIR", str(Path(__file__).resolve().parent.parent / ".dev-data"))


@pytest.fixture
def svc():
    from app.services import init_services

    return init_services()


@pytest.fixture
def meeting_notes(svc):
    pkg = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "resources"
        / "skill_market"
        / "packages"
        / "meeting_notes"
    )
    return svc.skill_installer.install_from_directory(pkg, replace=True)


def test_read_minutes_template(svc, meeting_notes):
    settings = svc.config.load_settings()
    result = svc.tool_runner.invoke(
        "read_skill_asset",
        {"skill_id": meeting_notes.id, "path": "minutes_template.md"},
        settings=settings,
        active_skills=[meeting_notes],
        dry_run=False,
    )
    assert result["status"] == "ok"
    assert "议题与结论" in result["content"]


def test_format_minutes_script(svc, meeting_notes):
    settings = svc.config.load_settings()
    settings.shell_tool_enabled = True
    payload = {
        "title": "Product Review",
        "participants": ["Alice", "Bob"],
        "topics": [{"topic": "Launch plan", "conclusion": "Go live next Friday"}],
        "todos": [{"task": "Update docs", "owner": "Alice", "due": "Friday"}],
    }
    result = svc.tool_runner.invoke(
        "run_skill_script",
        {
            "skill_id": meeting_notes.id,
            "script": "format_minutes.py",
            "arguments": payload,
        },
        settings=settings,
        active_skills=[meeting_notes],
        dry_run=False,
    )
    assert result["status"] == "ok"
    data = json.loads(result["stdout"])
    assert data["status"] == "ok"
    assert "Product Review" in data["markdown"]
    assert "Alice" in data["markdown"]
    assert "Launch plan" in data["markdown"]
