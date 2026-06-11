"""Skill 扩展工具：脚本执行、资产读取、资源列表."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.core.skills.skill import Skill
from app.core.skills.skill_package import MAX_SCRIPT_OUTPUT
from app.core.skills.skill_permissions import scripts_allowed
from app.core.tools.base import ToolContext

_TEXT_ASSET_SUFFIXES = {
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".csv",
    ".html",
    ".xml",
    ".py",
    ".ps1",
    ".bat",
    ".sh",
}
_MAX_ASSET_BYTES = 256_000


def _find_skill(ctx: ToolContext, skill_id: str) -> Skill | None:
    for skill in ctx.active_skills:
        if skill.id == skill_id:
            return skill
    return None


def _resolve_asset(skill: Skill, rel_path: str) -> Path | None:
    rel = rel_path.replace("\\", "/").lstrip("/")
    assets_dir = (skill.path / "assets").resolve()
    target = (assets_dir / rel).resolve()
    try:
        target.relative_to(assets_dir)
    except ValueError:
        return None
    return target if target.is_file() else None


def tool_list_skill_resources(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    skill_id = args.get("skill_id")
    skills = ctx.active_skills
    if skill_id:
        skill = _find_skill(ctx, skill_id)
        if not skill:
            return {"status": "error", "message": f"未激活 Skill: {skill_id}"}
        skills = [skill]

    if not skills:
        return {"status": "error", "message": "当前无激活的 Skill"}

    payload = []
    for skill in skills:
        pkg = skill.package
        payload.append(
            {
                "skill_id": skill.id,
                "name": skill.name,
                "agents": [
                    {"name": a.name, "description": a.description, "tools": a.tools}
                    for a in pkg.agents
                ],
                "scripts": [
                    {"filename": s.filename, "description": s.description}
                    for s in pkg.scripts
                ],
                "assets": [{"path": a.rel_path, "size": a.size} for a in pkg.assets],
                "references_loaded": bool(pkg.references_text),
            }
        )
    return {"status": "ok", "skills": payload}


def tool_read_skill_asset(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    skill_id = str(args.get("skill_id", ""))
    rel_path = str(args.get("path", ""))
    skill = _find_skill(ctx, skill_id)
    if not skill:
        return {"status": "error", "message": f"未激活 Skill: {skill_id}"}
    if not skill.package.has_assets:
        return {"status": "error", "message": "该 Skill 无 assets/"}

    target = _resolve_asset(skill, rel_path)
    if not target:
        return {"status": "error", "message": f"资产不存在: {rel_path}"}

    size = target.stat().st_size
    if size > _MAX_ASSET_BYTES:
        return {
            "status": "error",
            "message": f"资产过大 ({size} bytes)，上限 {_MAX_ASSET_BYTES}",
        }

    if target.suffix.lower() not in _TEXT_ASSET_SUFFIXES:
        return {
            "status": "error",
            "message": f"不支持的资产类型: {target.suffix}，仅支持文本类文件",
        }

    content = target.read_text(encoding="utf-8", errors="replace")
    return {
        "status": "ok",
        "skill_id": skill.id,
        "path": rel_path,
        "size": size,
        "content": content,
    }


def tool_run_skill_script(ctx: ToolContext, args: dict[str, Any]) -> dict[str, Any]:
    skill_id = str(args.get("skill_id", ""))
    script_name = str(args.get("script", ""))
    script_args = args.get("arguments") or {}

    skill = _find_skill(ctx, skill_id)
    if not skill:
        return {"status": "error", "message": f"未激活 Skill: {skill_id}"}

    settings = ctx.settings
    if settings is None:
        return {"status": "error", "message": "内部错误: 缺少 settings"}

    if not scripts_allowed(skill, settings):
        return {
            "status": "error",
            "message": "脚本执行未授权：需在 Skill 中声明 scripts/shell 权限并在设置中开启 Shell",
        }

    script_entry = next(
        (s for s in skill.package.scripts if s.filename == script_name),
        None,
    )
    if not script_entry:
        available = [s.filename for s in skill.package.scripts]
        return {
            "status": "error",
            "message": f"脚本不存在: {script_name}",
            "available": available,
        }

    script_path = script_entry.path
    scripts_dir = (skill.path / "scripts").resolve()
    try:
        script_path.relative_to(scripts_dir)
    except ValueError:
        return {"status": "error", "message": "脚本路径非法"}

    suffix = script_path.suffix.lower()
    stdin_payload: str | None = None
    if suffix == ".py":
        cmd = [sys.executable, str(script_path)]
        if script_args:
            stdin_payload = json.dumps(script_args, ensure_ascii=False)
    elif suffix == ".ps1":
        cmd = [
            "powershell",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
        ]
        if script_args:
            cmd.append(json.dumps(script_args, ensure_ascii=False))
    elif suffix in (".bat", ".cmd"):
        cmd = [str(script_path)]
    elif suffix == ".sh":
        cmd = ["bash", str(script_path)]
    else:
        return {"status": "error", "message": f"不支持的脚本类型: {suffix}"}

    try:
        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")
        proc = subprocess.run(
            cmd,
            cwd=str(scripts_dir),
            capture_output=True,
            text=True,
            input=stdin_payload,
            timeout=60,
            encoding="utf-8",
            errors="replace",
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "脚本执行超时 (60s)"}
    except OSError as e:
        return {"status": "error", "message": f"无法启动脚本: {e}"}

    stdout = (proc.stdout or "")[:MAX_SCRIPT_OUTPUT]
    stderr = (proc.stderr or "")[:MAX_SCRIPT_OUTPUT]
    ok = proc.returncode == 0
    return {
        "status": "ok" if ok else "error",
        "skill_id": skill.id,
        "script": script_name,
        "exit_code": proc.returncode,
        "stdout": stdout,
        "stderr": stderr,
    }
