"""Skill 安装包处理（标准目录：SKILL.md + agents/assets/references/scripts）."""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from app.core.skills.skill import Skill
from app.core.skills.skill_loader import SkillLoader
from app.core.skills.skill_layout import ensure_skill_layout
from app.core.skills.skill_parser import (
    SKILL_FILENAME,
    is_skill_directory,
    parse_skill_directory,
)


class SkillInstallError(Exception):
    pass


class SkillInstaller:
    def __init__(self, skills_dir: Path, loader: SkillLoader) -> None:
        self.skills_dir = skills_dir
        self.installed_dir = skills_dir / "installed"
        self.disabled_dir = skills_dir / "disabled"
        self.installed_dir.mkdir(parents=True, exist_ok=True)
        self.disabled_dir.mkdir(parents=True, exist_ok=True)
        self.loader = loader

    def validate_directory(self, skill_dir: Path) -> dict[str, Any]:
        skill_dir = skill_dir.resolve()
        if not is_skill_directory(skill_dir):
            raise SkillInstallError(f"缺少必要文件: {SKILL_FILENAME}")
        data = parse_skill_directory(skill_dir)
        if not data.get("name"):
            raise SkillInstallError(f"{SKILL_FILENAME} frontmatter 缺少 name 字段")
        return data

    def install_from_directory(self, source_dir: Path, *, replace: bool = False) -> Skill:
        source_dir = source_dir.resolve()
        data = self.validate_directory(source_dir)
        skill_id = data["id"]
        target = self.installed_dir / skill_id
        if target.exists() and not replace:
            raise SkillInstallError(f"Skill 已存在: {skill_id}，请先卸载或使用 replace=true")
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source_dir, target)
        ensure_skill_layout(target)
        self.loader.reload()
        return Skill.from_directory(target)

    def install_from_zip(self, zip_path: Path, *, replace: bool = False) -> Skill:
        zip_path = zip_path.resolve()
        if not zip_path.is_file():
            raise SkillInstallError("安装包不存在")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(tmp_path)

            skill_root = self._find_skill_root(tmp_path)
            return self.install_from_directory(skill_root, replace=replace)

    def install_from_bytes(self, data: bytes, filename: str = "skill.zip", *, replace: bool = False) -> Skill:
        with tempfile.TemporaryDirectory() as tmp:
            zip_path = Path(tmp) / filename
            zip_path.write_bytes(data)
            return self.install_from_zip(zip_path, replace=replace)

    def uninstall(self, skill_id: str) -> bool:
        target = self.installed_dir / skill_id
        if not target.exists():
            return False
        dest = self.disabled_dir / skill_id
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(target), str(dest))
        self.loader.reload()
        return True

    def _find_skill_root(self, extracted: Path) -> Path:
        if is_skill_directory(extracted):
            return extracted
        children = [p for p in extracted.iterdir() if p.is_dir()]
        for child in children:
            if is_skill_directory(child):
                return child
        raise SkillInstallError(f"安装包内未找到 {SKILL_FILENAME}")
