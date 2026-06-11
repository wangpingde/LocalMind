"""项目空间管理."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config.workspace import Workspace
from app.storage.sqlite_store import Project, SQLiteStore


def _slugify(name: str) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", name.strip().lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "project"


@dataclass
class ProjectInfo:
    id: str
    name: str
    description: str
    slug: str
    knowledge_path: str
    status: str
    created_at: str
    updated_at: str

    @classmethod
    def from_row(cls, row: Project) -> ProjectInfo:
        return cls(
            id=row.id,
            name=row.name,
            description=row.description or "",
            slug=row.slug,
            knowledge_path=row.knowledge_path or "",
            status=row.status or "active",
            created_at=row.created_at or "",
            updated_at=row.updated_at or "",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "slug": self.slug,
            "knowledge_path": self.knowledge_path,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class ProjectManager:
    def __init__(self, workspace: Workspace, sqlite: SQLiteStore) -> None:
        self.workspace = workspace
        self.sqlite = sqlite

    def list_projects(self, active_only: bool = True) -> list[ProjectInfo]:
        rows = self.sqlite.list_projects(active_only=active_only)
        return [ProjectInfo.from_row(r) for r in rows]

    def get_project(self, project_id: str) -> ProjectInfo | None:
        row = self.sqlite.get_project(project_id)
        return ProjectInfo.from_row(row) if row else None

    def create_project(self, name: str, description: str = "") -> ProjectInfo:
        slug = _slugify(name)
        existing = {p.slug for p in self.list_projects(active_only=False)}
        base_slug = slug
        n = 1
        while slug in existing:
            slug = f"{base_slug}-{n}"
            n += 1

        knowledge_path = self.workspace.knowledge_dir / "projects" / slug
        knowledge_path.mkdir(parents=True, exist_ok=True)

        row = self.sqlite.create_project(
            name=name,
            description=description,
            slug=slug,
            knowledge_path=str(knowledge_path),
        )
        return ProjectInfo.from_row(row)

    def update_project(
        self, project_id: str, name: str | None = None, description: str | None = None
    ) -> ProjectInfo | None:
        row = self.sqlite.update_project(project_id, name=name, description=description)
        return ProjectInfo.from_row(row) if row else None

    def delete_project(self, project_id: str) -> bool:
        return self.sqlite.delete_project(project_id)

    def path_prefix(self, project_id: str | None) -> str | None:
        """返回相对 knowledge 目录的路径前缀，与索引中 doc.path 格式一致."""
        if not project_id:
            return None
        project = self.get_project(project_id)
        if not project or project.status != "active":
            return None
        return f"projects/{project.slug}"

    @staticmethod
    def path_in_scope(doc_path: str, path_prefix: str | None) -> bool:
        if not path_prefix:
            return True
        doc_norm = str(doc_path).replace("\\", "/").strip("/")
        prefix_norm = path_prefix.replace("\\", "/").strip("/")
        if doc_norm == prefix_norm or doc_norm.startswith(f"{prefix_norm}/"):
            return True
        # 兼容绝对路径或含 knowledge/ 前缀的旧数据
        abs_prefix = prefix_norm
        if "/knowledge/" in doc_norm:
            suffix = doc_norm.split("/knowledge/", 1)[1]
            return suffix == prefix_norm or suffix.startswith(f"{prefix_norm}/")
        try:
            resolved = str(Path(doc_path).resolve()).replace("\\", "/")
            knowledge_marker = "/knowledge/"
            if knowledge_marker in resolved:
                suffix = resolved.split(knowledge_marker, 1)[1]
                return suffix == prefix_norm or suffix.startswith(f"{prefix_norm}/")
        except (OSError, ValueError):
            pass
        return False

    def matches_project_path(self, doc_path: str, project_id: str | None) -> bool:
        return self.path_in_scope(doc_path, self.path_prefix(project_id))
