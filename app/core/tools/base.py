"""工具基础类型."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.config.app_config import AppSettings
from app.config.workspace import Workspace
from app.core.rag.retriever import RAGEngine
from app.core.skills.skill import Skill
from app.security.permission_checker import PermissionChecker


@dataclass
class ToolContext:
    workspace: Workspace
    permission_checker: PermissionChecker
    rag: RAGEngine | None = None
    settings: AppSettings | None = None
    active_skills: list[Skill] = field(default_factory=list)
    project_path_prefix: str | None = None
    confirm_overwrite: bool = False


ToolHandler = Callable[[ToolContext, dict[str, Any]], dict[str, Any]]


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler
    requires_write: bool = False
    requires_read: bool = False

    def to_openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }
