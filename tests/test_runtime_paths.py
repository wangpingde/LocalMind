"""Runtime path behavior for packaged builds."""

from __future__ import annotations

from pathlib import Path


def test_app_resource_path_uses_source_tree():
    from app.config.runtime_paths import app_resource_path

    assert (app_resource_path("default_skills") / "local_knowledge_qa").is_dir()


def test_app_resource_path_uses_pyinstaller_meipass(monkeypatch, tmp_path):
    import app.config.runtime_paths as runtime_paths

    monkeypatch.setattr(runtime_paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(runtime_paths.sys, "_MEIPASS", str(tmp_path), raising=False)

    assert runtime_paths.app_resource_path("skill_market") == (
        tmp_path / "app" / "resources" / "skill_market"
    )


def test_linux_default_workspace_uses_xdg_data_home(monkeypatch, tmp_path):
    import app.config.workspace as workspace

    monkeypatch.delenv("LOCALMIND_DATA_DIR", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr(workspace.os, "name", "posix", raising=False)
    monkeypatch.setattr(workspace.sys, "platform", "linux", raising=False)

    assert workspace.get_default_workspace() == (tmp_path / "LocalMind").resolve()


def test_linux_default_workspace_falls_back_to_local_share(monkeypatch):
    import app.config.workspace as workspace

    monkeypatch.delenv("LOCALMIND_DATA_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.setattr(workspace.os, "name", "posix", raising=False)
    monkeypatch.setattr(workspace.sys, "platform", "linux", raising=False)

    expected = Path.home() / ".local" / "share" / "LocalMind"
    assert workspace.get_default_workspace() == expected.resolve()
