"""工具与输出文件路由."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import get_services

router = APIRouter(tags=["tools"])


class BatchRequest(BaseModel):
    operation: str
    source_dir: str = "outputs"
    source_glob: str = ""
    dest_dir: str = ""
    output_path: str = ""
    pattern: str = "{stem}_{index:03d}{suffix}"
    dry_run: bool = True
    overwrite: bool = False


@router.get("/tools")
def list_tools():
    svc = get_services()
    return [
        {"name": t.name, "description": t.description}
        for t in svc.tool_registry.list_tools()
    ]


@router.get("/outputs")
def list_outputs(recursive: bool = True):
    svc = get_services()
    root = svc.workspace.outputs_dir.resolve()
    files: list[dict] = []
    iterator = root.rglob("*") if recursive else root.glob("*")
    for p in sorted(iterator):
        if p.is_file():
            rel = str(p.relative_to(svc.workspace.root)).replace("\\", "/")
            files.append(
                {
                    "path": rel,
                    "name": p.name,
                    "size": p.stat().st_size,
                    "modified_at": p.stat().st_mtime,
                }
            )
    return {"output_dir": str(root), "files": files, "count": len(files)}


@router.post("/tools/batch")
def run_batch(req: BatchRequest):
    svc = get_services()
    settings = svc.config.load_settings()
    result = svc.tool_runner.invoke(
        "batch_process_files",
        req.model_dump(),
        settings=settings,
        confirm_overwrite=req.overwrite,
    )
    if result.get("status") == "error":
        raise HTTPException(400, result.get("message", "批处理失败"))
    return result
