"""Skill 标准目录完整加载测试."""

from __future__ import annotations

from pathlib import Path

from app.core.agent.context_builder import ContextBuilder
from app.core.skills.skill import Skill
from app.core.skills.skill_activator import SkillActivator
from app.core.skills.skill_package import load_skill_package


def test_load_file_organizer_package():
    root = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "resources"
        / "skill_market"
        / "packages"
        / "file_organizer"
    )
    data, pkg = load_skill_package(root)
    assert data["id"] == "file_organizer"
    assert pkg.body
    assert pkg.references_text
    assert any(a.name == "preview_planner" for a in pkg.agents)
    assert any(s.filename == "preview.py" for s in pkg.scripts)
    assert any(a.rel_path == "report_template.md" for a in pkg.assets)


def test_activator_includes_all_sections():
    root = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "resources"
        / "skill_market"
        / "packages"
        / "file_organizer"
    )
    skill = Skill.from_directory(root)
    text = SkillActivator().build_sections([skill])
    assert "子 Agent 流程" in text
    assert "preview_planner" in text
    assert "参考资料 (references/)" in text
    assert "preview.py" in text
    assert "report_template.md" in text
    assert "list_files" in text


def test_context_builder_uses_activator():
    from app.config.app_config import AppSettings

    root = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "resources"
        / "skill_market"
        / "packages"
        / "file_organizer"
    )
    skill = Skill.from_directory(root)
    built = ContextBuilder().build(
        user_input="整理文件",
        history=[],
        skills=[skill],
        memories=[],
        rag_results=[],
        settings=AppSettings(),
    )
    assert "Active Skills" in built.system_prompt
    assert "run_skill_script" in built.system_prompt
    assert "workflow.md" in built.system_prompt
