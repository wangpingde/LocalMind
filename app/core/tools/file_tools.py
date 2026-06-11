"""内置文件与知识库工具."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.tools.base import ToolContext
from app.core.tools.file_batch import FileBatchProcessor, normalize_rel_path, safe_relative

DEFAULT_READ_PATTERNS = ["knowledge/**", "memory/**", "outputs/**"]
DEFAULT_WRITE_PATTERNS = ["outputs/**"]

_processor = FileBatchProcessor()
_MAX_READ_BYTES = 512_000


def _workspace_root(ctx: ToolContext) -> Path:
    return ctx.workspace.root.resolve()


def _resolve_path(ctx: ToolContext, rel_path: str) -> Path:
    """解析为工作区内的绝对路径；兼容 knowledge 子目录简写."""
    raw = (rel_path or "").strip()
    if not raw:
        return _workspace_root(ctx)

    root = _workspace_root(ctx)
    candidate = Path(raw)
    if candidate.is_absolute():
        resolved = candidate.resolve()
        try:
            resolved.relative_to(root)
            return resolved
        except ValueError:
            pass

    rel = normalize_rel_path(raw)
    direct = (root / rel).resolve()
    if direct.exists():
        return direct

    knowledge = ctx.workspace.knowledge_dir.resolve()
    if not rel.startswith("knowledge/"):
        nested = (knowledge / rel).resolve()
        try:
            nested.relative_to(knowledge)
            return nested
        except ValueError:
            pass

    return direct


def _read_patterns(ctx: ToolContext) -> list[str]:
    patterns = list(DEFAULT_READ_PATTERNS)
    for skill in ctx.active_skills:
        extra = skill.permissions.get("file_read") or skill.permissions.get("read_paths")
        if isinstance(extra, list):
            patterns.extend(extra)
        elif isinstance(extra, str) and extra:
            patterns.append(extra)
    return patterns


def _write_patterns(ctx: ToolContext) -> list[str]:
    patterns = list(DEFAULT_WRITE_PATTERNS)
    for skill in ctx.active_skills:
        extra = skill.permissions.get("file_write") or skill.permissions.get("file_write_paths")
        if isinstance(extra, list):
            patterns.extend(extra)
        elif isinstance(extra, str) and extra:
            patterns.append(extra)
    return patterns


def _check_read(ctx: ToolContext, path: Path) -> dict[str, Any] | None:
    patterns = _read_patterns(ctx)
    if ctx.permission_checker.check_path_access(path, patterns, "file_read"):
        return None
    root = _workspace_root(ctx)
    try:
        rel = path.relative_to(root).as_posix()
    except ValueError:
        rel = str(path)
    hint = (
        "路径需相对于工作区，知识库文件请使用 knowledge/... 前缀"
        "（例如 knowledge/inbox/文档.md）"
    )
    return {
        "status": "error",
        "message": "无读取权限",
        "path": rel,
        "allowed_patterns": patterns,
        "hint": hint,
    }


def _check_write(ctx: ToolContext, path: Path) -> dict[str, Any] | None:
    if not ctx.permission_checker.check_path_access(path, _write_patterns(ctx), "file_write"):
        return {"status": "error", "message": "无写入权限"}
    return None


def tool_read_file(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_path(ctx, args.get("path", ""))
    err = _check_read(ctx, path)
    if err:
        return err
    if not path.is_file():
        return {"status": "error", "message": f"文件不存在: {safe_relative(path, _workspace_root(ctx))}"}
    size = path.stat().st_size
    if size > _MAX_READ_BYTES:
        return {
            "status": "error",
            "message": f"文件过大 ({size} bytes)，上限 {_MAX_READ_BYTES}",
        }
    content = path.read_text(encoding="utf-8", errors="replace")
    return {
        "status": "ok",
        "path": safe_relative(path, _workspace_root(ctx)),
        "size": size,
        "content": content,
    }


def tool_write_file(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_path(ctx, args.get("path", ""))
    content = args.get("content", "")
    overwrite = bool(args.get("overwrite", False))
    err = _check_write(ctx, path)
    if err:
        return err
    if path.exists() and not overwrite and not ctx.confirm_overwrite:
        return {
            "status": "needs_confirmation",
            "message": "文件已存在，需确认覆盖",
            "path": safe_relative(path, _workspace_root(ctx)),
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return {
        "status": "ok",
        "path": safe_relative(path, _workspace_root(ctx)),
        "bytes_written": len(content.encode("utf-8")),
        "overwritten": path.exists(),
    }


def tool_list_files(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    dir_path = _resolve_path(ctx, args.get("directory", "outputs"))
    err = _check_read(ctx, dir_path)
    if err:
        return err
    if not dir_path.exists():
        return {"status": "error", "message": "目录不存在"}
    recursive = bool(args.get("recursive", False))
    pattern = args.get("pattern", "*")
    root = _workspace_root(ctx)
    if dir_path.is_file():
        return {"status": "error", "message": "路径是文件而非目录"}

    files: list[dict[str, Any]] = []
    iterator = dir_path.rglob(pattern) if recursive else dir_path.glob(pattern)
    for p in sorted(iterator):
        if p.is_file():
            files.append(
                {
                    "path": safe_relative(p, root),
                    "name": p.name,
                    "size": p.stat().st_size,
                }
            )
    return {"status": "ok", "directory": safe_relative(dir_path, root), "files": files, "count": len(files)}


def tool_mkdir(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_path(ctx, args.get("path", ""))
    err = _check_write(ctx, path)
    if err:
        return err
    path.mkdir(parents=True, exist_ok=True)
    return {"status": "ok", "path": safe_relative(path, _workspace_root(ctx))}


def tool_move_file(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    import shutil

    src = _resolve_path(ctx, args.get("source", ""))
    dest = _resolve_path(ctx, args.get("destination", ""))
    if err := _check_read(ctx, src):
        return err
    if err := _check_write(ctx, dest):
        return err
    if not src.exists():
        return {"status": "error", "message": "源文件不存在"}
    if dest.exists() and not ctx.confirm_overwrite:
        return {"status": "needs_confirmation", "message": "目标已存在，需确认覆盖"}
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dest))
    root = _workspace_root(ctx)
    return {
        "status": "ok",
        "source": safe_relative(src, root),
        "destination": safe_relative(dest, root),
    }


def tool_search_knowledge(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    if not ctx.rag:
        return {"status": "error", "message": "知识库检索不可用"}
    query = args.get("query", "").strip()
    if not query:
        return {"status": "error", "message": "query 不能为空"}
    top_k = int(args.get("top_k", 5))
    resp = ctx.rag.retrieve(query, top_k=top_k, path_prefix=ctx.project_path_prefix)
    return {
        "status": "ok",
        "query": query,
        "results": ctx.rag.to_dict(resp)["results"],
    }


def tool_organize_files(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    directory = args.get("directory", "outputs")
    strategy = args.get("strategy", "by_extension")
    dry_run = bool(args.get("dry_run", False))
    dir_path = _resolve_path(ctx, directory)
    if err := _check_write(ctx, dir_path):
        return err
    if strategy == "by_date":
        report = _processor.organize_by_date(dir_path, dry_run=dry_run)
    else:
        report = _processor.organize_by_extension(dir_path, dry_run=dry_run)
    return {"status": "ok", "dry_run": dry_run, **report.to_dict()}


def tool_batch_process_files(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    operation = args.get("operation", "organize_by_extension")
    source_dir = args.get("source_dir", "outputs")
    source_glob = args.get("source_glob", "")
    dest_dir = args.get("dest_dir", "")
    output_path = args.get("output_path", "")
    pattern = args.get("pattern", "{stem}_{index:03d}{suffix}")
    dry_run = bool(args.get("dry_run", False))
    overwrite = bool(args.get("overwrite", False)) or ctx.confirm_overwrite

    root = _workspace_root(ctx)
    check_path = _resolve_path(ctx, source_dir or "outputs")
    if err := _check_write(ctx, check_path):
        return err
    if output_path:
        if err := _check_write(ctx, _resolve_path(ctx, output_path)):
            return err
    if dest_dir:
        if err := _check_write(ctx, _resolve_path(ctx, dest_dir)):
            return err

    report = _processor.batch_process(
        root,
        operation=operation,
        source_glob=source_glob or f"{normalize_rel_path(source_dir)}/**/*",
        source_dir=source_dir,
        dest_dir=dest_dir,
        output_path=output_path,
        pattern=pattern,
        dry_run=dry_run,
        overwrite=overwrite,
    )
    return {"status": "ok", "dry_run": dry_run, **report.to_dict()}
