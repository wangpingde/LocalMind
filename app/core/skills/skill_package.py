"""Skill 标准目录完整加载（agents / assets / references / scripts）."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from app.core.skills.skill_parser import (
    REFERENCE_GLOB,
    STANDARD_SUBDIRS,
    load_references,
    parse_skill_md,
    skill_md_path,
)

AGENT_GLOB = ("*.yaml", "*.yml", "*.md")
SCRIPT_EXTENSIONS = (".py", ".ps1", ".bat", ".sh")
MAX_ASSET_LIST = 40
MAX_SCRIPT_OUTPUT = 32_000


@dataclass
class SkillAgent:
    name: str
    description: str
    instructions: str
    tools: list[str] = field(default_factory=list)


@dataclass
class SkillScript:
    filename: str
    description: str
    path: Path


@dataclass
class SkillAsset:
    rel_path: str
    path: Path
    size: int


@dataclass
class SkillPackage:
    body: str
    references_text: str
    agents: list[SkillAgent] = field(default_factory=list)
    scripts: list[SkillScript] = field(default_factory=list)
    assets: list[SkillAsset] = field(default_factory=list)

    @property
    def has_scripts(self) -> bool:
        return bool(self.scripts)

    @property
    def has_assets(self) -> bool:
        return bool(self.assets)


def _parse_agent_file(path: Path) -> SkillAgent | None:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".md",):
        meta, body = parse_skill_md(text)
        if not meta.get("name"):
            meta["name"] = path.stem
        return SkillAgent(
            name=str(meta["name"]),
            description=str(meta.get("description") or ""),
            instructions=body.strip() or str(meta.get("instructions") or ""),
            tools=list(meta.get("tools") or []),
        )
    meta = yaml.safe_load(text) or {}
    if not isinstance(meta, dict) or not meta.get("name"):
        return None
    instructions = str(meta.get("instructions") or meta.get("prompt") or "")
    return SkillAgent(
        name=str(meta["name"]),
        description=str(meta.get("description") or ""),
        instructions=instructions.strip(),
        tools=[str(t) for t in (meta.get("tools") or []) if t],
    )


def _load_agents(skill_dir: Path) -> list[SkillAgent]:
    agents_dir = skill_dir / "agents"
    if not agents_dir.is_dir():
        return []
    result: list[SkillAgent] = []
    for pattern in AGENT_GLOB:
        for path in sorted(agents_dir.glob(pattern)):
            if not path.is_file() or path.name.startswith("."):
                continue
            try:
                agent = _parse_agent_file(path)
                if agent:
                    result.append(agent)
            except OSError:
                continue
    return result


def _script_description(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    for line in text.splitlines()[:12]:
        s = line.strip()
        if s.startswith("#") and len(s) > 1:
            return s.lstrip("#").strip()
        if s.startswith('"""') or s.startswith("'''"):
            return s.strip("\"'").strip()
    return path.stem.replace("_", " ")


def _load_scripts(skill_dir: Path) -> list[SkillScript]:
    scripts_dir = skill_dir / "scripts"
    if not scripts_dir.is_dir():
        return []
    manifest = scripts_dir / "manifest.yaml"
    if manifest.is_file():
        try:
            data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
            entries = data.get("scripts") or []
            result: list[SkillScript] = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                fname = entry.get("file") or entry.get("name")
                if not fname:
                    continue
                path = scripts_dir / str(fname)
                if path.is_file():
                    result.append(
                        SkillScript(
                            filename=path.name,
                            description=str(entry.get("description") or _script_description(path)),
                            path=path.resolve(),
                        )
                    )
            if result:
                return result
        except (OSError, yaml.YAMLError):
            pass

    result = []
    for path in sorted(scripts_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SCRIPT_EXTENSIONS:
            continue
        if path.name == "manifest.yaml":
            continue
        result.append(
            SkillScript(
                filename=path.name,
                description=_script_description(path),
                path=path.resolve(),
            )
        )
    return result


def _load_assets(skill_dir: Path) -> list[SkillAsset]:
    assets_dir = skill_dir / "assets"
    if not assets_dir.is_dir():
        return []
    result: list[SkillAsset] = []
    for path in sorted(assets_dir.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        try:
            rel = path.relative_to(assets_dir).as_posix()
            size = path.stat().st_size
        except (OSError, ValueError):
            continue
        result.append(SkillAsset(rel_path=rel, path=path.resolve(), size=size))
        if len(result) >= MAX_ASSET_LIST:
            break
    return result


def load_skill_package(skill_dir: Path) -> tuple[dict[str, Any], SkillPackage]:
    """解析 SKILL.md 元数据 + 标准子目录."""
    raw = skill_md_path(skill_dir).read_text(encoding="utf-8")
    meta, body = parse_skill_md(raw)

    from app.core.skills.skill_parser import (
        normalize_triggers,
        resolve_skill_id,
    )

    keywords, intents = normalize_triggers(meta)
    package = SkillPackage(
        body=body.strip(),
        references_text=load_references(skill_dir),
        agents=_load_agents(skill_dir),
        scripts=_load_scripts(skill_dir),
        assets=_load_assets(skill_dir),
    )

    data = {
        "id": resolve_skill_id(meta, skill_dir),
        "name": str(meta.get("name") or meta.get("title") or skill_dir.name),
        "version": str(meta.get("version") or "1.0.0"),
        "description": str(meta.get("description") or ""),
        "triggers_keywords": keywords,
        "triggers_intent": intents,
        "capabilities": list(meta.get("capabilities") or []),
        "permissions": dict(meta.get("permissions") or {}),
    }
    return data, package
