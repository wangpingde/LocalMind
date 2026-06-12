"""项目空间路由."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import get_services

router = APIRouter(tags=["projects"])


class ProjectCreate(BaseModel):
    name: str
    description: str = ""


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


@router.get("/projects")
def list_projects():
    svc = get_services()
    return [p.to_dict() for p in svc.projects.list_projects()]


@router.post("/projects")
def create_project(payload: ProjectCreate):
    svc = get_services()
    if not payload.name.strip():
        raise HTTPException(400, "项目名称不能为空")
    project = svc.projects.create_project(payload.name.strip(), payload.description.strip())
    svc.audit.log("project_created", {"project_id": project.id, "name": project.name})
    return project.to_dict()


@router.get("/projects/{project_id}")
def get_project(project_id: str):
    svc = get_services()
    project = svc.projects.get_project(project_id)
    if not project:
        raise HTTPException(404, "项目不存在")
    return project.to_dict()


@router.put("/projects/{project_id}")
def update_project(project_id: str, payload: ProjectUpdate):
    svc = get_services()
    project = svc.projects.update_project(
        project_id, name=payload.name, description=payload.description
    )
    if not project:
        raise HTTPException(404, "项目不存在")
    svc.audit.log("project_updated", {"project_id": project.id})
    return project.to_dict()


@router.delete("/projects/{project_id}")
def delete_project(project_id: str):
    svc = get_services()
    if not svc.projects.delete_project(project_id, indexer=svc.indexer):
        raise HTTPException(404, "项目不存在")
    svc.audit.log("project_deleted", {"project_id": project_id})
    return {"status": "ok"}
