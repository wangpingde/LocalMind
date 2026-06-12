"""知识库路由."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.rag.index_progress import begin as progress_begin
from app.core.rag.index_progress import finish as progress_finish
from app.core.rag.index_progress import snapshot as index_progress_snapshot
from app.core.rag.index_progress import step as progress_step
from app.core.rag.media_refs import resolve_media_absolute
from app.core.rag.parser import DocParser
from app.services import get_services

router = APIRouter(tags=["knowledge"])

_ALLOWED_SUBDIRS = frozenset({"", "inbox", "work", "personal", "projects"})


class ReindexRequest(BaseModel):
    path: str | None = None


def _validate_project_subdir(svc, sub: str) -> None:
    if not sub.startswith("projects/"):
        return
    slug = sub.split("/", 1)[1].strip("/")
    if not slug or "/" in slug:
        raise HTTPException(400, "非法项目路径")
    if not any(p.slug == slug for p in svc.projects.list_projects()):
        raise HTTPException(400, f"项目不存在: {slug}")


def _resolve_upload_path(knowledge_dir: Path, subdir: str, filename: str) -> Path:
    sub = subdir.replace("\\", "/").strip("/")
    if sub and sub not in _ALLOWED_SUBDIRS - {""}:
        if not sub.startswith("projects/"):
            raise HTTPException(400, f"不支持的目录: {subdir}")
    if ".." in sub or sub.startswith("/"):
        raise HTTPException(400, "非法子目录")

    safe_name = Path(filename).name
    if not safe_name or safe_name in (".", ".."):
        raise HTTPException(400, "非法文件名")

    target_dir = (knowledge_dir / sub).resolve() if sub else knowledge_dir.resolve()
    root = knowledge_dir.resolve()
    try:
        target_dir.relative_to(root)
    except ValueError:
        raise HTTPException(400, "非法保存路径") from None

    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / safe_name


@router.get("/knowledge/progress")
def knowledge_progress():
    return index_progress_snapshot()


@router.get("/knowledge/formats")
def supported_formats():
    return {"formats": sorted(DocParser.SUPPORTED)}


@router.get("/knowledge/media")
def get_knowledge_media(path: str = Query(..., description="相对 knowledge 目录的媒体路径")):
    svc = get_services()
    rel = path.replace("\\", "/").strip()
    if not rel or ".." in rel or rel.startswith("/"):
        raise HTTPException(400, "非法路径")
    resolved = resolve_media_absolute(svc.workspace.knowledge_dir, rel)
    if not resolved:
        raise HTTPException(404, "媒体文件不存在")
    return FileResponse(resolved)


@router.get("/knowledge/documents")
def list_documents(project_id: str | None = Query(None)):
    svc = get_services()
    docs = svc.sqlite.list_documents()
    if project_id:
        docs = [
            d
            for d in docs
            if svc.projects.matches_project_path(d.path, project_id)
        ]
    indexed = sum(1 for d in docs if d.status == "indexed")
    failed = sum(1 for d in docs if d.status == "failed")
    last_indexed = max((d.indexed_at for d in docs if d.indexed_at), default=None)
    return {
        "knowledge_path": str(svc.workspace.knowledge_dir),
        "total": len(docs),
        "indexed": indexed,
        "failed": failed,
        "last_indexed_at": last_indexed,
        "documents": [
            {
                "id": d.id,
                "path": d.path,
                "filename": d.filename,
                "file_type": d.file_type,
                "size": d.size,
                "status": d.status,
                "indexed_at": d.indexed_at,
                "error_message": d.error_message,
            }
            for d in docs
        ],
    }


@router.post("/knowledge/upload")
async def upload_documents(
    subdir: str = Query("inbox", description="保存到 knowledge/ 下的子目录"),
    reindex: bool = Query(True, description="上传后是否立即索引"),
    files: list[UploadFile] = File(...),
):
    if not files:
        raise HTTPException(400, "未选择文件")

    svc = get_services()
    knowledge_dir = svc.workspace.knowledge_dir
    sub = subdir.replace("\\", "/").strip("/")
    _validate_project_subdir(svc, sub)
    saved: list[dict] = []
    errors: list[dict] = []
    valid_uploads = [
        u for u in files if (u.filename or "") and Path(u.filename).suffix.lower() in DocParser.SUPPORTED
    ]
    total = len(valid_uploads)
    progress_begin("upload", total=total or 1, message="正在上传文档...")

    try:
        for upload in files:
            filename = upload.filename or ""
            suffix = Path(filename).suffix.lower()
            if suffix not in DocParser.SUPPORTED:
                errors.append(
                    {
                        "filename": filename,
                        "message": f"不支持的文件类型: {suffix or '(无扩展名)'}",
                    }
                )
                continue

            try:
                target = _resolve_upload_path(knowledge_dir, subdir, filename)
                data = await upload.read()
                if not data:
                    errors.append({"filename": filename, "message": "空文件"})
                    continue
                target.write_bytes(data)
                rel_path = str(target.relative_to(knowledge_dir.resolve())).replace("\\", "/")
                index_result = None
                if reindex:
                    progress_step(
                        current=len(saved) + 1,
                        message=f"正在索引 ({len(saved) + 1}/{total or 1}): {target.name}",
                    )
                    try:
                        index_result = svc.indexer.index_file(target)
                    except Exception as e:
                        index_result = "failed"
                        errors.append({"filename": filename, "message": f"索引失败: {e}"})
                saved.append(
                    {
                        "filename": target.name,
                        "path": rel_path,
                        "size": len(data),
                        "index_result": index_result,
                    }
                )
            except HTTPException:
                raise
            except OSError as e:
                errors.append({"filename": filename, "message": str(e)})
    finally:
        progress_finish()

    return {
        "status": "ok" if saved else "error",
        "saved": saved,
        "errors": errors,
        "reindexed": reindex,
    }


@router.delete("/knowledge/documents/{document_id}")
def delete_document(
    document_id: str,
    reindex: bool = Query(False, description="删除后是否全量重建索引"),
):
    svc = get_services()
    result = svc.indexer.delete_document_file(document_id)
    if result.get("status") != "ok":
        raise HTTPException(404, str(result.get("message", "删除失败")))

    stats = None
    if reindex:
        stats = svc.indexer.index_directory()

    return {"status": "ok", "deleted": result, "reindex_stats": stats}


@router.post("/knowledge/reindex")
def reindex(req: ReindexRequest):
    svc = get_services()
    stats = svc.indexer.index_directory(req.path, force=True)
    return {"status": "ok", "stats": stats}


@router.delete("/knowledge/index")
def clear_index():
    svc = get_services()
    svc.indexer.clear_index()
    return {"status": "ok"}


@router.post("/knowledge/open-folder")
def open_folder():
    svc = get_services()
    path = str(svc.workspace.knowledge_dir)
    if sys.platform == "win32":
        subprocess.Popen(["explorer", path])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
    return {"status": "ok", "path": path}
