"""Skill 标准格式解析测试."""

from __future__ import annotations

from pathlib import Path

from app.core.skills.skill import Skill
from app.core.skills.skill_layout import ensure_skill_layout
from app.core.skills.skill_parser import (
    is_skill_directory,
    normalize_triggers,
    parse_skill_md,
    resolve_skill_id,
)


def test_parse_skill_md_frontmatter():
    text = """---
id: demo
name: Demo Skill
description: test
triggers:
  keywords: [hello, world]
version: 2.0.0
---

# Body

Do work.
"""
    meta, body = parse_skill_md(text)
    assert meta["id"] == "demo"
    assert "Do work" in body
    kw, intent = normalize_triggers(meta)
    assert "hello" in kw


def test_from_directory_builtin():
    root = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "resources"
        / "default_skills"
        / "local_knowledge_qa"
    )
    assert is_skill_directory(root)
    skill = Skill.from_directory(root)
    assert skill.id == "local_knowledge_qa"
    assert "本地知识问答" in skill.prompt
    assert "根据资料" in skill.triggers_keywords
    assert skill.package.agents
    assert skill.package.scripts
    assert skill.package.assets


def test_standard_layout_dirs(tmp_path):
    skill_dir = tmp_path / "demo_skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nid: demo\nname: Demo\ndescription: x\ntriggers: [a]\n---\n\nbody",
        encoding="utf-8",
    )
    ensure_skill_layout(skill_dir)
    for sub in ("agents", "assets", "references", "scripts"):
        assert (skill_dir / sub).is_dir()
    assert (skill_dir / "LICENSE").exists()
    assert resolve_skill_id({"name": "my-skill"}, skill_dir) == "my_skill"
