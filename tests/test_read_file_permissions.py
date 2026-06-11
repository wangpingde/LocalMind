"""read_file 路径与权限测试."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("LOCALMIND_DATA_DIR", str(Path(__file__).resolve().parent.parent / ".dev-data"))


@pytest.fixture
def svc():
    from app.services import init_services

    return init_services()


def test_read_file_knowledge_shorthand_path(svc, tmp_path, monkeypatch):
    monkeypatch.setattr(svc.workspace, "root", tmp_path)
    monkeypatch.setattr(svc.workspace, "knowledge_dir", tmp_path / "knowledge")
    inbox = tmp_path / "knowledge" / "inbox"
    inbox.mkdir(parents=True)
    (inbox / "note.md").write_text("hello", encoding="utf-8")

    skill = next(s for s in svc.skill_loader.get_cached() if s.id == "local_knowledge_qa")
    settings = svc.config.load_settings()
    result = svc.tool_runner.invoke(
        "read_file",
        {"path": "inbox/note.md"},
        settings=settings,
        active_skills=[skill],
        dry_run=False,
    )
    assert result["status"] == "ok"
    assert "hello" in result["content"]


def test_read_file_blocked_by_skill_whitelist(svc, tmp_path, monkeypatch):
    monkeypatch.setattr(svc.workspace, "root", tmp_path)
    out = tmp_path / "outputs"
    out.mkdir(parents=True)
    (out / "a.txt").write_text("x", encoding="utf-8")

    pkg = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "resources"
        / "skill_market"
        / "packages"
        / "file_organizer"
    )
    skill = svc.skill_installer.install_from_directory(pkg, replace=True)
    settings = svc.config.load_settings()
    result = svc.tool_runner.invoke(
        "read_file",
        {"path": "outputs/a.txt"},
        settings=settings,
        active_skills=[skill],
        dry_run=False,
    )
    assert result["status"] == "error"
    assert "权限范围" in result["message"]
