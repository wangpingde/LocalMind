"""工作区目录初始化与管理."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from loguru import logger

from app.core.skills.skill_layout import ensure_skill_layout
from app.core.skills.skill_package import load_skill_package
from app.core.skills.skill_parser import is_skill_directory

DEFAULT_PORT = 17777
SERVICE_NAME = "LocalMind"


def get_default_workspace() -> Path:
    """返回默认工作区路径."""
    override = os.environ.get("LOCALMIND_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path.home() / "Library" / "Application Support"

    return (base / SERVICE_NAME).resolve()


class Workspace:
    """管理工作区目录结构."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or get_default_workspace()).resolve()
        self.config_dir = self.root / "config"
        self.knowledge_dir = self.root / "knowledge"
        self.memory_dir = self.root / "memory"
        self.skills_dir = self.root / "skills"
        self.vector_store_dir = self.root / "vector_store"
        self.database_dir = self.root / "database"
        self.outputs_dir = self.root / "outputs"
        self.logs_dir = self.root / "logs"

    def ensure(self) -> None:
        """创建完整工作区目录结构."""
        dirs = [
            self.config_dir,
            self.knowledge_dir / "inbox",
            self.knowledge_dir / "work",
            self.knowledge_dir / "personal",
            self.knowledge_dir / "projects",
            self.memory_dir / "archive",
            self.skills_dir / "installed",
            self.skills_dir / "disabled",
            self.vector_store_dir,
            self.database_dir,
            self.outputs_dir / "documents",
            self.outputs_dir / "reports",
            self.outputs_dir / "exports",
            self.logs_dir,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

        self._ensure_default_configs()
        self._ensure_permissions_config()
        self._ensure_builtin_skills()
        logger.info("工作区已就绪: {}", self.root)

    def _ensure_default_configs(self) -> None:
        app_yaml = self.config_dir / "app.yaml"
        if not app_yaml.exists():
            app_yaml.write_text(
                """workspace_dir: ""
knowledge_dir: ""
memory_dir: ""
skills_dir: ""
output_dir: ""
api_port: 17777
local_only_mode: true
send_file_path_to_model: false
send_memory_to_model: true
auto_memory_enabled: true
skill_network_enabled: false
shell_tool_enabled: false
tools_enabled: true
agent_max_steps: 8
auto_confirm_file_write: false
""",
                encoding="utf-8",
            )

        providers_yaml = self.config_dir / "model_providers.yaml"
        if not providers_yaml.exists():
            providers_yaml.write_text(
                """
default:
  type: openai_compatible
  base_url: "http://47.236.4.250:9782/openai-api/v1"
  chat_model: "gpt-4o-mini"
  embedding_model: "text-embedding-3-small"
  temperature: 0.7
  max_tokens: 16384
  
local_ollama:
  type: ollama
  base_url: "http://localhost:11434"
  chat_model: "qwen2.5:14b"
  embedding_model: "nomic-embed-text"
  temperature: 0.7
  max_tokens: 4096
""",
                encoding="utf-8",
            )

    def _ensure_permissions_config(self) -> None:
        permissions_yaml = self.config_dir / "permissions.yaml"
        if not permissions_yaml.exists():
            permissions_yaml.write_text(
                """# 全局 Skill 权限策略（v0.2）
skill_network_enabled: false
shell_tool_enabled: false
local_only_mode: true
default_read_paths:
  - knowledge/**
  - memory/**
deny_paths:
  - config/**
  - database/**
""",
                encoding="utf-8",
            )

    @staticmethod
    def _builtin_skill_needs_upgrade(bundled: Path, installed: Path) -> bool:
        if not is_skill_directory(installed):
            return True
        try:
            _, bundled_pkg = load_skill_package(bundled)
            _, installed_pkg = load_skill_package(installed)
        except OSError:
            return False
        return (
            len(bundled_pkg.agents) > len(installed_pkg.agents)
            or len(bundled_pkg.scripts) > len(installed_pkg.scripts)
            or len(bundled_pkg.assets) > len(installed_pkg.assets)
            or bool(bundled_pkg.references_text) != bool(installed_pkg.references_text)
        )

    def _ensure_builtin_skills(self) -> None:
        """将内置 Skill 复制到工作区（若不存在或 bundled 资源更完整）."""
        bundled = Path(__file__).resolve().parent.parent / "resources" / "default_skills"
        if not bundled.exists():
            return
        installed = self.skills_dir / "installed"
        for skill_dir in bundled.iterdir():
            if not skill_dir.is_dir() or not is_skill_directory(skill_dir):
                continue
            target = installed / skill_dir.name
            if target.exists() and self._builtin_skill_needs_upgrade(skill_dir, target):
                shutil.rmtree(target)
                logger.info("升级内置 Skill: {}", skill_dir.name)
            if not target.exists():
                shutil.copytree(skill_dir, target)
                ensure_skill_layout(target)
                logger.info("已安装内置 Skill: {}", skill_dir.name)

    @property
    def db_path(self) -> Path:
        return self.database_dir / "app.sqlite"

    @property
    def audit_db_path(self) -> Path:
        return self.database_dir / "audit.sqlite"
