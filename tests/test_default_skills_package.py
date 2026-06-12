"""内置默认 Skill 标准目录完整性测试."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.skills.skill import Skill
from app.core.skills.skill_package import load_skill_package

BUNDLED = Path(__file__).resolve().parents[1] / "app" / "resources" / "default_skills"

EXPECTED = {
    "local_knowledge_qa": {
        "agent": "knowledge_researcher",
        "script": "summarize_sources.py",
        "asset": "citation_template.md",
    },
    "personal_writer": {
        "agent": "content_drafter",
        "script": "outline.py",
        "asset": "email_template.md",
    },
    "product_architect": {
        "agent": "prd_planner",
        "script": "task_breakdown.py",
        "asset": "prd_template.md",
    },
    "restaurant_expert_system": {
        "agent": "expert_diagnosis_orchestrator",
        "script": "expert_route.py",
        "asset": "expert_diagnosis_canvas.md",
    },
}


@pytest.mark.parametrize("skill_id", list(EXPECTED.keys()))
def test_builtin_skill_package(skill_id: str):
    root = BUNDLED / skill_id
    data, pkg = load_skill_package(root)
    assert data["id"] == skill_id
    assert pkg.body
    assert pkg.references_text
    assert pkg.agents
    assert pkg.scripts
    assert pkg.assets

    exp = EXPECTED[skill_id]
    assert any(a.name == exp["agent"] for a in pkg.agents)
    assert any(s.filename == exp["script"] for s in pkg.scripts)
    assert any(a.rel_path == exp["asset"] for a in pkg.assets)

    skill = Skill.from_directory(root)
    perms = skill.permissions
    assert perms.get("scripts")
    tools = perms.get("tools") or []
    assert "list_skill_resources" in tools
    assert "run_skill_script" in tools
