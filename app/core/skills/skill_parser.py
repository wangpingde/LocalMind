"""SKILL.md 解析（标准 Skill 目录格式）."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

SKILL_FILENAME = "SKILL.md"
STANDARD_SUBDIRS = ("agents", "assets", "references", "scripts")
REFERENCE_GLOB = "*.md"
MAX_REFERENCE_CHARS = 12_000

_FRONTMATTER_RE = re.compile(
    r"^---\s*\r?\n(.*?)\r?\n---\s*\r?\n?(.*)",
    re.DOTALL,
)


def skill_md_path(skill_dir: Path) -> Path:
    return skill_dir / SKILL_FILENAME


def is_skill_directory(skill_dir: Path) -> bool:
    return skill_md_path(skill_dir).is_file()


def parse_skill_md(text: str) -> tuple[dict[str, Any], str]:
    """解析 SKILL.md，返回 (frontmatter, body_markdown)."""
    stripped = text.strip()
    if not stripped:
        return {}, ""

    match = _FRONTMATTER_RE.match(stripped)
    if not match:
        return {}, stripped

    meta_raw, body = match.group(1), match.group(2)
    meta = yaml.safe_load(meta_raw) or {}
    if not isinstance(meta, dict):
        meta = {}
    return meta, body.strip()


def normalize_triggers(meta: dict[str, Any]) -> tuple[list[str], list[str]]:
    """从 frontmatter 提取 triggers.keywords / triggers.intent."""
    triggers = meta.get("triggers") or {}
    keywords: list[str] = []
    intents: list[str] = []

    if isinstance(triggers, list):
        keywords = [str(t) for t in triggers if t]
    elif isinstance(triggers, dict):
        raw_kw = triggers.get("keywords") or []
        raw_intent = triggers.get("intent") or []
        if isinstance(raw_kw, list):
            keywords = [str(t) for t in raw_kw if t]
        if isinstance(raw_intent, list):
            intents = [str(t) for t in raw_intent if t]

    return keywords, intents


def resolve_skill_id(meta: dict[str, Any], skill_dir: Path) -> str:
    if meta.get("id"):
        return str(meta["id"])
    name = meta.get("name")
    if name:
        return str(name).replace("-", "_").replace(" ", "_").lower()
    return skill_dir.name


def load_references(skill_dir: Path) -> str:
    """加载 references/ 下 Markdown 作为补充上下文."""
    ref_dir = skill_dir / "references"
    if not ref_dir.is_dir():
        return ""

    parts: list[str] = []
    total = 0
    for path in sorted(ref_dir.glob(REFERENCE_GLOB)):
        if not path.is_file():
            continue
        try:
            chunk = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if not chunk:
            continue
        header = f"### {path.name}\n"
        block = header + chunk
        if total + len(block) > MAX_REFERENCE_CHARS:
            remain = MAX_REFERENCE_CHARS - total
            if remain > 100:
                parts.append(block[:remain] + "\n...")
            break
        parts.append(block)
        total += len(block)

    if not parts:
        return ""
    return "\n\n".join(parts)


def build_prompt(body: str, references_text: str) -> str:
    if not references_text:
        return body
    return f"{body}\n\n## References\n\n{references_text}"


def parse_skill_directory(skill_dir: Path) -> dict[str, Any]:
    """从标准 Skill 目录解析全部字段."""
    md_path = skill_md_path(skill_dir)
    raw = md_path.read_text(encoding="utf-8")
    meta, body = parse_skill_md(raw)
    keywords, intents = normalize_triggers(meta)
    refs = load_references(skill_dir)
    return {
        "id": resolve_skill_id(meta, skill_dir),
        "name": str(meta.get("name") or meta.get("title") or skill_dir.name),
        "version": str(meta.get("version") or "1.0.0"),
        "description": str(meta.get("description") or ""),
        "prompt": build_prompt(body, refs),
        "triggers_keywords": keywords,
        "triggers_intent": intents,
        "capabilities": list(meta.get("capabilities") or []),
        "permissions": dict(meta.get("permissions") or {}),
    }
