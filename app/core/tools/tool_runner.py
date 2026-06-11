"""工具调用运行时."""

from __future__ import annotations

import json
from typing import Any

from app.config.app_config import AppSettings
from app.config.workspace import Workspace
from app.core.rag.retriever import RAGEngine
from app.core.skills.skill import Skill
from app.core.tools.base import ToolContext
from app.core.skills.skill_permissions import is_tool_allowed
from app.core.tools.registry import ToolRegistry
from app.security.audit_logger import AuditLogger
from app.security.permission_checker import PermissionChecker


class ToolRunner:
    """权限校验 → 执行 → 审计."""

    def __init__(
        self,
        registry: ToolRegistry,
        workspace: Workspace,
        permission_checker: PermissionChecker,
        audit: AuditLogger,
        rag: RAGEngine | None = None,
    ) -> None:
        self.registry = registry
        self.workspace = workspace
        self.permission_checker = permission_checker
        self.audit = audit
        self.rag = rag

    def _make_context(
        self,
        settings: AppSettings,
        active_skills: list[Skill] | None = None,
        project_path_prefix: str | None = None,
        confirm_overwrite: bool = False,
    ) -> ToolContext:
        return ToolContext(
            workspace=self.workspace,
            permission_checker=self.permission_checker,
            rag=self.rag,
            settings=settings,
            active_skills=active_skills or [],
            project_path_prefix=project_path_prefix,
            confirm_overwrite=confirm_overwrite or settings.auto_confirm_file_write,
        )

    def invoke(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        skill_id: str = "",
        *,
        settings: AppSettings | None = None,
        active_skills: list[Skill] | None = None,
        project_path_prefix: str | None = None,
        dry_run: bool = False,
        confirm_overwrite: bool = False,
    ) -> dict[str, Any]:
        from app.config.app_config import AppSettings as _Settings

        settings = settings or _Settings()
        if not settings.tools_enabled and not dry_run:
            result = {"status": "error", "message": "工具调用已在设置中禁用"}
            self.audit.log_tool_call(
                tool_name=tool_name,
                arguments=arguments,
                skill_id=skill_id,
                result=result,
                dry_run=False,
            )
            return result

        if dry_run:
            result = {
                "status": "skipped",
                "message": "dry_run 模式，仅记录审计",
            }
            self.audit.log_tool_call(
                tool_name=tool_name,
                arguments=arguments,
                skill_id=skill_id,
                result=result,
                dry_run=True,
            )
            return result

        if active_skills and not is_tool_allowed(tool_name, active_skills):
            skill_names = ", ".join(s.name for s in active_skills)
            result = {
                "status": "error",
                "message": (
                    f"工具 {tool_name} 不在当前 Skill 权限范围内"
                    f"（已激活: {skill_names}）"
                ),
                "hint": "请在对应 Skill 的 SKILL.md 的 permissions.tools 中加入该工具，"
                "或换用已授权的工具（如 search_knowledge、read_skill_asset）",
            }
            self.audit.log_tool_call(
                tool_name=tool_name,
                arguments=arguments,
                skill_id=skill_id,
                result=result,
                dry_run=False,
            )
            return result

        ctx = self._make_context(
            settings,
            active_skills=active_skills,
            project_path_prefix=project_path_prefix,
            confirm_overwrite=confirm_overwrite,
        )
        result = self.registry.execute(ctx, tool_name, arguments)
        self.audit.log_tool_call(
            tool_name=tool_name,
            arguments=arguments,
            skill_id=skill_id,
            result=result,
            dry_run=False,
        )
        return result

    @staticmethod
    def format_tool_result(result: dict[str, Any]) -> str:
        return json.dumps(result, ensure_ascii=False)
