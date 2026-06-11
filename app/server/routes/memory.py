"""记忆路由."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import get_services

router = APIRouter(tags=["memory"])


class MemoryCreate(BaseModel):
    type: str
    content: str
    tags: list[str] = []


class MemoryUpdate(BaseModel):
    type: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    status: str | None = None


@router.get("/memories")
def list_memories(type: str | None = None, keyword: str | None = None):
    svc = get_services()
    memories = svc.memory.list_all(memory_type=type, keyword=keyword)
    return [svc.memory.memory_to_dict(m) for m in memories]


@router.post("/memories")
def create_memory(req: MemoryCreate):
    svc = get_services()
    mem = svc.memory.upsert_memory(req.type, req.content, req.tags)
    svc.audit.log("memory_created", {"memory_id": mem.id})
    return svc.memory.memory_to_dict(mem)


@router.put("/memories/{memory_id}")
def update_memory(memory_id: str, req: MemoryUpdate):
    svc = get_services()
    kwargs = req.model_dump(exclude_none=True)
    if not kwargs:
        raise HTTPException(400, "无更新内容")
    updated = svc.sqlite.update_memory(memory_id, **kwargs)
    if not updated:
        raise HTTPException(404, "记忆不存在")
    svc.memory._sync_vector(updated)
    svc.audit.log("memory_updated", {"memory_id": memory_id})
    return svc.memory.memory_to_dict(updated)


@router.delete("/memories/{memory_id}")
def delete_memory(memory_id: str):
    svc = get_services()
    if not svc.memory.delete_memory(memory_id):
        raise HTTPException(404, "记忆不存在")
    svc.audit.log("memory_deleted", {"memory_id": memory_id})
    return {"status": "ok"}
