"""Skill 选择器."""

from __future__ import annotations

from app.config.app_config import AppSettings
from app.core.skills.skill import Skill
from app.core.skills.skill_loader import SkillLoader
from app.security.audit_logger import AuditLogger
from app.security.permission_checker import PermissionChecker


class SkillSelector:
    def __init__(
        self,
        loader: SkillLoader,
        permission_checker: PermissionChecker,
        audit: AuditLogger,
    ) -> None:
        self.loader = loader
        self.permission_checker = permission_checker
        self.audit = audit

    def select(
        self,
        user_input: str,
        settings: AppSettings,
        top_n: int = 3,
    ) -> list[Skill]:
        skills = [s for s in self.loader.get_cached() if s.enabled]
        skills = self.permission_checker.filter_allowed_skills(skills, settings)
        if not skills:
            return []

        scored: list[tuple[float, Skill]] = []
        query_lower = user_input.lower()

        for skill in skills:
            score = 0.0
            for kw in skill.triggers_keywords:
                if kw.lower() in query_lower:
                    score += 1.0 + len(kw) * 0.01
            if score > 0:
                scored.append((score, skill))

        scored.sort(key=lambda x: x[0], reverse=True)
        selected = [s for _, s in scored[:top_n]]
        if selected:
            self.audit.log(
                "skill_selected",
                {
                    "skills": [s.id for s in selected],
                    "filtered_by_permission": True,
                },
            )
        return selected
