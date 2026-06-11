"""Skill 路由."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config.runtime_paths import app_resource_path
from app.core.skills.skill_installer import SkillInstallError
from app.core.skills.skill_package import load_skill_package
from app.core.skills.skill_parser import is_skill_directory
from app.core.skills.skill_presenter import enrich_skill_dict
from app.services import get_services

router = APIRouter(tags=["skills"])

_MARKET_ROOT = app_resource_path("skill_market")


def _package_preview(package_dir: Path) -> dict:
    if not package_dir.is_dir() or not is_skill_directory(package_dir):
        return {
            "has_references": False,
            "agents_count": 0,
            "scripts_count": 0,
            "assets_count": 0,
        }
    try:
        _, pkg = load_skill_package(package_dir)
        return {
            "has_references": bool(pkg.references_text),
            "agents_count": len(pkg.agents),
            "scripts_count": len(pkg.scripts),
            "assets_count": len(pkg.assets),
        }
    except OSError:
        return {
            "has_references": False,
            "agents_count": 0,
            "scripts_count": 0,
            "assets_count": 0,
        }


@router.get("/skills")
def list_skills():
    svc = get_services()
    settings = svc.config.load_settings()
    skills = []
    for skill in svc.skill_loader.get_cached():
        skills.append(
            enrich_skill_dict(skill, svc.permission_checker, settings)
        )
    return skills


@router.post("/skills/reload")
def reload_skills():
    svc = get_services()
    skills = svc.skill_loader.reload()
    return {"status": "ok", "count": len(skills)}


@router.post("/skills/{skill_id}/enable")
def enable_skill(skill_id: str):
    svc = get_services()
    rec = svc.sqlite.set_skill_enabled(skill_id, True)
    if not rec:
        raise HTTPException(404, "Skill 不存在")
    svc.skill_loader.reload()
    svc.audit.log("skill_enabled", {"skill_id": skill_id})
    return {"status": "ok"}


@router.post("/skills/{skill_id}/disable")
def disable_skill(skill_id: str):
    svc = get_services()
    rec = svc.sqlite.set_skill_enabled(skill_id, False)
    if not rec:
        raise HTTPException(404, "Skill 不存在")
    svc.skill_loader.reload()
    svc.audit.log("skill_disabled", {"skill_id": skill_id})
    return {"status": "ok"}


@router.get("/skills/market")
def skill_market():
    catalog_path = _MARKET_ROOT / "catalog.json"
    if not catalog_path.exists():
        return {"version": "0.3", "skills": []}
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    svc = get_services()
    installed = {s.id for s in svc.skill_loader.get_cached()}
    for item in data.get("skills", []):
        item["installed"] = item.get("id") in installed
        package_dir = _MARKET_ROOT / "packages" / item.get("package_dir", item.get("id", ""))
        item["package"] = _package_preview(package_dir)
    return data


@router.get("/skills/{skill_id}")
def get_skill(skill_id: str):
    svc = get_services()
    settings = svc.config.load_settings()
    skill = next((s for s in svc.skill_loader.get_cached() if s.id == skill_id), None)
    if not skill:
        raise HTTPException(404, "Skill 不存在")
    return enrich_skill_dict(skill, svc.permission_checker, settings)


@router.post("/skills/market/{skill_id}/install")
def install_from_market(skill_id: str, replace: bool = False):
    svc = get_services()
    catalog_path = _MARKET_ROOT / "catalog.json"
    if not catalog_path.exists():
        raise HTTPException(404, "市场目录不存在")
    data = json.loads(catalog_path.read_text(encoding="utf-8"))
    entry = next((s for s in data.get("skills", []) if s.get("id") == skill_id), None)
    if not entry:
        raise HTTPException(404, "市场 Skill 不存在")
    package_dir = _MARKET_ROOT / "packages" / entry.get("package_dir", skill_id)
    if not package_dir.exists():
        raise HTTPException(404, "安装包缺失")
    try:
        skill = svc.skill_installer.install_from_directory(package_dir, replace=replace)
        svc.audit.log("skill_installed", {"skill_id": skill.id, "source": "market"})
        return {"status": "ok", "skill": skill.to_dict()}
    except SkillInstallError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/skills/install")
async def install_skill_zip(file: UploadFile = File(...), replace: bool = False):
    svc = get_services()
    data = await file.read()
    if not data:
        raise HTTPException(400, "空文件")
    try:
        skill = svc.skill_installer.install_from_bytes(
            data, filename=file.filename or "skill.zip", replace=replace
        )
        svc.audit.log("skill_installed", {"skill_id": skill.id, "source": "upload"})
        return {"status": "ok", "skill": skill.to_dict()}
    except SkillInstallError as e:
        raise HTTPException(400, str(e)) from e


@router.delete("/skills/{skill_id}/uninstall")
def uninstall_skill(skill_id: str):
    svc = get_services()
    if not svc.skill_installer.uninstall(skill_id):
        raise HTTPException(404, "Skill 未安装")
    svc.audit.log("skill_uninstalled", {"skill_id": skill_id})
    return {"status": "ok"}


@router.post("/skills/open-folder")
def open_skills_folder():
    svc = get_services()
    path = str(svc.workspace.skills_dir / "installed")
    if sys.platform == "win32":
        subprocess.Popen(["explorer", path])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
    return {"status": "ok", "path": path}
