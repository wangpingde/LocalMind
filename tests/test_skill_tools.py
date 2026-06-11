"""Skill 扩展工具端到端测试."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("LOCALMIND_DATA_DIR", str(Path(__file__).resolve().parent.parent / ".dev-data"))


@pytest.fixture
def svc():
    from app.services import init_services

    return init_services()


@pytest.fixture
def file_organizer(svc):
    pkg = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "resources"
        / "skill_market"
        / "packages"
        / "file_organizer"
    )
    return svc.skill_installer.install_from_directory(pkg, replace=True)


def test_list_skill_resources(svc, file_organizer):
    settings = svc.config.load_settings()
    result = svc.tool_runner.invoke(
        "list_skill_resources",
        {"skill_id": file_organizer.id},
        settings=settings,
        active_skills=[file_organizer],
        dry_run=False,
    )
    assert result["status"] == "ok"
    skills = result["skills"]
    assert len(skills) == 1
    entry = skills[0]
    assert entry["skill_id"] == "file_organizer"
    assert any(a["name"] == "preview_planner" for a in entry["agents"])
    assert any(s["filename"] == "preview.py" for s in entry["scripts"])
    assert any(a["path"] == "report_template.md" for a in entry["assets"])
    assert entry["references_loaded"] is True


def test_read_skill_asset(svc, file_organizer):
    settings = svc.config.load_settings()
    result = svc.tool_runner.invoke(
        "read_skill_asset",
        {"skill_id": file_organizer.id, "path": "report_template.md"},
        settings=settings,
        active_skills=[file_organizer],
        dry_run=False,
    )
    assert result["status"] == "ok"
    assert "文件整理报告" in result["content"]


def test_run_skill_script_preview(svc, file_organizer, tmp_path, monkeypatch):
    monkeypatch.setattr(svc.workspace, "root", tmp_path)
    inbox = tmp_path / "outputs" / "inbox"
    inbox.mkdir(parents=True)
    (inbox / "a.txt").write_text("a", encoding="utf-8")
    (inbox / "b.md").write_text("b", encoding="utf-8")

    settings = svc.config.load_settings()
    settings.shell_tool_enabled = True

    result = svc.tool_runner.invoke(
        "run_skill_script",
        {
            "skill_id": file_organizer.id,
            "script": "preview.py",
            "arguments": {"directory": str(inbox)},
        },
        settings=settings,
        active_skills=[file_organizer],
        dry_run=False,
    )
    assert result["status"] == "ok"
    assert result["exit_code"] == 0
    assert "total_files" in result["stdout"]
    assert '"total_files": 2' in result["stdout"] or "total_files\": 2" in result["stdout"]


def test_run_skill_script_blocked_without_shell(svc, file_organizer):
    settings = svc.config.load_settings()
    settings.shell_tool_enabled = False
    result = svc.tool_runner.invoke(
        "run_skill_script",
        {"skill_id": file_organizer.id, "script": "preview.py"},
        settings=settings,
        active_skills=[file_organizer],
        dry_run=False,
    )
    assert result["status"] == "error"
    assert "Shell" in result["message"] or "脚本" in result["message"]
