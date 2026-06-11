"""Skill 数据模型."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.skills.skill_package import SkillPackage, load_skill_package
from app.core.skills.skill_parser import is_skill_directory


@dataclass
class Skill:
    id: str
    name: str
    version: str
    description: str
    prompt: str
    path: Path
    package: SkillPackage
    triggers_keywords: list[str] = field(default_factory=list)
    triggers_intent: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    permissions: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    @classmethod
    def from_directory(cls, skill_dir: Path, enabled: bool = True) -> Skill:
        if not is_skill_directory(skill_dir):
            raise FileNotFoundError(f"缺少标准 Skill 文件 SKILL.md: {skill_dir}")
        data, package = load_skill_package(skill_dir)
        return cls(
            id=data["id"],
            name=data["name"],
            version=data["version"],
            description=data["description"],
            prompt=package.body,
            path=skill_dir,
            package=package,
            triggers_keywords=data["triggers_keywords"],
            triggers_intent=data["triggers_intent"],
            capabilities=data["capabilities"],
            permissions=data["permissions"],
            enabled=enabled,
        )

    def to_dict(self) -> dict[str, Any]:
        pkg = self.package
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "path": str(self.path),
            "enabled": self.enabled,
            "triggers_keywords": self.triggers_keywords,
            "triggers_intent": self.triggers_intent,
            "capabilities": self.capabilities,
            "permissions": self.permissions,
            "format": "skill-md",
            "agents": [
                {"name": a.name, "description": a.description, "tools": a.tools}
                for a in pkg.agents
            ],
            "scripts": [
                {"filename": s.filename, "description": s.description} for s in pkg.scripts
            ],
            "assets": [{"path": a.rel_path, "size": a.size} for a in pkg.assets],
            "package": {
                "has_references": bool(pkg.references_text),
                "agents_count": len(pkg.agents),
                "scripts_count": len(pkg.scripts),
                "assets_count": len(pkg.assets),
            },
        }
