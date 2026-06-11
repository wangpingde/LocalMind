"""Skill 加载器."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from app.core.skills.skill import Skill
from app.core.skills.skill_parser import is_skill_directory
from app.storage.sqlite_store import SQLiteStore


class SkillLoader:
    def __init__(self, skills_dir: Path, sqlite: SQLiteStore) -> None:
        self.skills_dir = skills_dir
        self.installed_dir = skills_dir / "installed"
        self.sqlite = sqlite
        self._cache: list[Skill] = []

    def load_all(self) -> list[Skill]:
        self._cache = []
        if not self.installed_dir.exists():
            return []

        db_skills = {s.id: s for s in self.sqlite.list_skills()}

        for skill_dir in sorted(self.installed_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            if not is_skill_directory(skill_dir):
                continue
            try:
                db_rec = db_skills.get(skill_dir.name)
                enabled = bool(db_rec.enabled) if db_rec else True
                skill = Skill.from_directory(skill_dir, enabled=enabled)
                self._cache.append(skill)
                self.sqlite.upsert_skill(
                    id=skill.id,
                    name=skill.name,
                    version=skill.version,
                    description=skill.description,
                    path=str(skill.path),
                    enabled=1 if enabled else 0,
                )
            except Exception as e:
                logger.error("加载 Skill 失败 {}: {}", skill_dir, e)

        logger.info("已加载 {} 个 Skill", len(self._cache))
        return self._cache

    def get_cached(self) -> list[Skill]:
        if not self._cache:
            return self.load_all()
        return self._cache

    def reload(self) -> list[Skill]:
        self._cache = []
        return self.load_all()
