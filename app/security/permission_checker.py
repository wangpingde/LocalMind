"""Skill 权限检查."""

from __future__ import annotations

import fnmatch
from pathlib import Path
from typing import Any

from app.config.app_config import AppSettings
from app.config.workspace import Workspace
from app.core.skills.skill import Skill
from app.security.audit_logger import AuditLogger


class PermissionChecker:
    def __init__(self, workspace: Workspace, audit: AuditLogger) -> None:
        self.workspace = workspace
        self.audit = audit

    def is_skill_allowed(
        self, skill: Skill, settings: AppSettings, *, write_audit: bool = True
    ) -> bool:
        perms = skill.permissions or {}
        reasons: list[str] = []

        if self._capability_enabled(perms.get("network")) and not settings.skill_network_enabled:
            reasons.append("全局已禁用网络权限")
        if self._capability_enabled(perms.get("shell")) and not settings.shell_tool_enabled:
            reasons.append("全局已禁用 Shell 权限")

        file_read = perms.get("file_read") or perms.get("read_paths")
        if isinstance(file_read, list) and file_read:
            if not self._validate_path_rules(file_read):
                reasons.append("file_read 路径规则无效")

        if reasons:
            if write_audit:
                self.audit.log_permission_denied(
                    skill_id=skill.id,
                    skill_name=skill.name,
                    reasons=reasons,
                    permissions=perms,
                )
            return False
        return True

    def check_path_access(
        self,
        target_path: str | Path,
        allowed_patterns: list[str],
        permission_type: str = "file_read",
    ) -> bool:
        path = Path(target_path).resolve()
        ok = self._path_matches(path, allowed_patterns)
        if not ok:
            self.audit.log_permission_denied(
                skill_id="",
                skill_name="",
                reasons=[f"路径不在 {permission_type} 允许范围内"],
                permissions={"path": str(path), "allowed": allowed_patterns},
            )
        return ok

    def filter_allowed_skills(self, skills: list[Skill], settings: AppSettings) -> list[Skill]:
        return [s for s in skills if self.is_skill_allowed(s, settings)]

    def summarize_permissions(self, skill: Skill) -> dict[str, Any]:
        perms = skill.permissions or {}
        lines: list[str] = []
        if PermissionChecker._capability_enabled(perms.get("network")):
            lines.append("网络访问")
        if PermissionChecker._capability_enabled(perms.get("shell")):
            lines.append("Shell 执行")
        if PermissionChecker._capability_enabled(perms.get("scripts")):
            lines.append("Skill 脚本执行")
        tools = perms.get("tools")
        if isinstance(tools, list) and tools:
            lines.append("限定工具: " + ", ".join(str(t) for t in tools))
        write_paths = perms.get("file_write") or perms.get("file_write_paths")
        if write_paths:
            lines.append("文件写入")
        read_paths = perms.get("file_read") or perms.get("read_paths")
        if read_paths:
            if isinstance(read_paths, list):
                lines.append("可读路径: " + ", ".join(read_paths))
            else:
                lines.append(f"可读路径: {read_paths}")
        write_paths = perms.get("file_write_paths") or perms.get("write_paths")
        if write_paths:
            if isinstance(write_paths, list):
                lines.append("可写路径: " + ", ".join(write_paths))
            else:
                lines.append(f"可写路径: {write_paths}")
        if not lines:
            lines.append("无特殊权限（仅 Prompt 注入）")
        return {"raw": perms, "summary": lines}

    @staticmethod
    def _capability_enabled(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, dict):
            return bool(value.get("enabled", False))
        return False

    def _validate_path_rules(self, patterns: list[str]) -> bool:
        return bool(patterns) and all(isinstance(p, str) and p.strip() for p in patterns)

    def _path_matches(self, path: Path, patterns: list[str]) -> bool:
        root = self.workspace.root.resolve()
        try:
            rel = path.relative_to(root)
            rel_str = str(rel).replace("\\", "/")
        except ValueError:
            rel_str = str(path).replace("\\", "/")

        abs_str = str(path).replace("\\", "/")
        for pattern in patterns:
            pat = pattern.replace("\\", "/")
            if fnmatch.fnmatch(rel_str, pat) or fnmatch.fnmatch(abs_str, f"*/{pat}"):
                return True
            if pat.endswith("/**") or pat.endswith("**"):
                base_str = pat.replace("/**", "").replace("**", "").rstrip("/")
                base = (root / base_str).resolve()
                try:
                    path.relative_to(base)
                    return True
                except ValueError:
                    continue
            candidate = (root / pat).resolve()
            if path == candidate:
                return True
        return False
