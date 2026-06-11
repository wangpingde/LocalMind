"""v0.3 功能测试."""

from __future__ import annotations

import os
import zipfile
from pathlib import Path

import pytest

os.environ.setdefault("LOCALMIND_DATA_DIR", str(Path(__file__).resolve().parent.parent / ".dev-data"))


@pytest.fixture
def svc():
    from app.services import init_services

    return init_services()


def test_tool_registry_builtins(svc):
    names = {t.name for t in svc.tool_registry.list_tools()}
    assert "read_file" in names
    assert "write_file" in names
    assert "batch_process_files" in names
    assert "organize_files" in names


def test_write_and_list_file(svc, tmp_path, monkeypatch):
    monkeypatch.setattr(svc.workspace, "root", tmp_path)
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "outputs").mkdir()
    settings = svc.config.load_settings()
    result = svc.tool_runner.invoke(
        "write_file",
        {"path": "outputs/hello.txt", "content": "你好", "overwrite": True},
        settings=settings,
        confirm_overwrite=True,
        dry_run=False,
    )
    assert result["status"] == "ok"
    listed = svc.tool_runner.invoke(
        "list_files",
        {"directory": "outputs"},
        settings=settings,
        dry_run=False,
    )
    assert listed["count"] >= 1


def test_batch_organize_by_extension(svc, tmp_path, monkeypatch):
    monkeypatch.setattr(svc.workspace, "root", tmp_path)
    out = tmp_path / "outputs" / "inbox"
    out.mkdir(parents=True)
    (out / "a.txt").write_text("a", encoding="utf-8")
    (out / "b.md").write_text("b", encoding="utf-8")
    settings = svc.config.load_settings()
    preview = svc.tool_runner.invoke(
        "batch_process_files",
        {
            "operation": "organize_by_extension",
            "source_dir": "outputs/inbox",
            "dry_run": True,
        },
        settings=settings,
        dry_run=False,
    )
    assert preview["status"] == "ok"
    assert preview["total"] == 2
    done = svc.tool_runner.invoke(
        "batch_process_files",
        {
            "operation": "organize_by_extension",
            "source_dir": "outputs/inbox",
            "dry_run": False,
        },
        settings=settings,
        dry_run=False,
    )
    assert done["succeeded"] == 2
    assert (out / "txt" / "a.txt").exists()
    assert (out / "md" / "b.md").exists()


def test_merge_text_files(svc, tmp_path, monkeypatch):
    monkeypatch.setattr(svc.workspace, "root", tmp_path)
    src = tmp_path / "outputs" / "src"
    src.mkdir(parents=True)
    (src / "1.md").write_text("# A", encoding="utf-8")
    (src / "2.md").write_text("# B", encoding="utf-8")
    settings = svc.config.load_settings()
    result = svc.tool_runner.invoke(
        "batch_process_files",
        {
            "operation": "merge_text",
            "source_glob": "outputs/src/*.md",
            "output_path": "outputs/merged.md",
        },
        settings=settings,
        dry_run=False,
    )
    assert result["status"] == "ok"
    merged = tmp_path / "outputs" / "merged.md"
    assert merged.exists()
    text = merged.read_text(encoding="utf-8")
    assert "# A" in text and "# B" in text


def test_skill_market_api(client):
    resp = client.get("/api/skills/market")
    assert resp.status_code == 200
    skills = resp.json().get("skills", [])
    ids = {s["id"] for s in skills}
    assert "file_organizer" in ids
    fo = next(s for s in skills if s["id"] == "file_organizer")
    pkg = fo.get("package") or {}
    assert pkg.get("agents_count", 0) >= 1
    assert pkg.get("scripts_count", 0) >= 1
    assert pkg.get("assets_count", 0) >= 1
    mn = next(s for s in skills if s["id"] == "meeting_notes")
    mn_pkg = mn.get("package") or {}
    assert mn_pkg.get("agents_count", 0) >= 1
    assert mn_pkg.get("scripts_count", 0) >= 1


def test_skill_detail_api(client, svc):
    pkg = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "resources"
        / "skill_market"
        / "packages"
        / "file_organizer"
    )
    svc.skill_installer.install_from_directory(pkg, replace=True)
    resp = client.get("/api/skills/file_organizer")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "file_organizer"
    assert any(a["name"] == "preview_planner" for a in data.get("agents", []))
    assert any(s["filename"] == "preview.py" for s in data.get("scripts", []))


def test_skill_install_from_market(svc):
    skill = svc.skill_installer.install_from_directory(
        Path(__file__).resolve().parents[1]
        / "app"
        / "resources"
        / "skill_market"
        / "packages"
        / "file_organizer",
        replace=True,
    )
    assert skill.id == "file_organizer"


def test_skill_install_zip(svc, tmp_path):
    pkg = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "resources"
        / "skill_market"
        / "packages"
        / "meeting_notes"
    )
    zip_path = tmp_path / "meeting_notes.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        for f in pkg.rglob("*"):
            if f.is_file():
                zf.write(f, f.relative_to(pkg))
    skill = svc.skill_installer.install_from_zip(zip_path, replace=True)
    assert skill.id == "meeting_notes"


@pytest.fixture
def client():
    from app.server.api import create_app
    from app.services import init_services
    from fastapi.testclient import TestClient

    init_services()
    with TestClient(create_app()) as test_client:
        yield test_client


def test_tools_list_api(client):
    resp = client.get("/api/tools")
    assert resp.status_code == 200
    assert any(t["name"] == "write_file" for t in resp.json())


def test_skill_meta_tools(svc):
    names = {t.name for t in svc.tool_registry.list_tools()}
    assert "list_skill_resources" in names
    assert "read_skill_asset" in names
    assert "run_skill_script" in names


def test_tool_whitelist_blocks_unauthorized(svc):
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
        {"path": "outputs/hello.txt"},
        settings=settings,
        active_skills=[skill],
        dry_run=False,
    )
    assert result["status"] == "error"
    assert "权限" in result["message"]
