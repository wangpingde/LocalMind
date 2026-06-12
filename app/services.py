"""应用服务容器."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from loguru import logger

from app.config.app_config import ConfigManager
from app.config.workspace import Workspace
from app.core.agent.agent_runtime import AgentRuntime
from app.core.llm.model_gateway import ModelGateway
from app.core.memory.memory_manager import MemoryManager
from app.core.project.project_manager import ProjectManager
from app.core.rag.indexer import DocumentIndexer
from app.core.rag.retriever import RAGEngine
from app.core.skills.skill_loader import SkillLoader
from app.core.skills.skill_selector import SkillSelector
from app.core.skills.skill_installer import SkillInstaller
from app.core.tools.registry import ToolRegistry
from app.core.tools.tool_runner import ToolRunner
from app.security.audit_logger import AuditLogger
from app.security.permission_checker import PermissionChecker
from app.storage.file_watcher import FileWatcher
from app.storage.lancedb_store import LanceDBStore
from app.storage.sqlite_store import SQLiteStore

INIT_TIMEOUT_SEC = 120


@dataclass
class AppServices:
    workspace: Workspace
    config: ConfigManager
    sqlite: SQLiteStore
    vector_store: LanceDBStore
    audit: AuditLogger
    model_gateway: ModelGateway
    rag: RAGEngine
    memory: MemoryManager
    skill_loader: SkillLoader
    skill_selector: SkillSelector
    projects: ProjectManager
    permission_checker: PermissionChecker
    tool_registry: ToolRegistry
    tool_runner: ToolRunner
    skill_installer: SkillInstaller
    indexer: DocumentIndexer
    agent: AgentRuntime
    file_watcher: FileWatcher | None = None


_services: AppServices | None = None
_services_ready = threading.Event()
_services_lock = threading.Lock()
_init_error: str | None = None


def init_services(workspace: Workspace | None = None) -> AppServices:
    global _services, _init_error
    with _services_lock:
        if _services is not None:
            return _services

        ws = workspace or Workspace()
        ws.ensure()

        config = ConfigManager(ws)
        sqlite = SQLiteStore(ws)
        vector_store = LanceDBStore(ws.vector_store_dir)
        audit = AuditLogger(ws)
        model_gateway = ModelGateway(config)
        rag = RAGEngine(vector_store, sqlite, model_gateway, ws.knowledge_dir)
        memory = MemoryManager(sqlite, vector_store, model_gateway)
        skill_loader = SkillLoader(ws.skills_dir, sqlite)
        skill_loader.load_all()
        permission_checker = PermissionChecker(ws, audit)
        skill_selector = SkillSelector(skill_loader, permission_checker, audit)
        projects = ProjectManager(ws, sqlite)
        tool_registry = ToolRegistry()
        tool_runner = ToolRunner(
            tool_registry, ws, permission_checker, audit, rag=rag
        )
        skill_installer = SkillInstaller(ws.skills_dir, skill_loader)
        indexer = DocumentIndexer(ws, sqlite, vector_store, model_gateway, audit)
        agent = AgentRuntime(
            config,
            model_gateway,
            rag,
            memory,
            skill_selector,
            sqlite,
            audit,
            projects,
            tool_runner,
            tool_registry,
        )
        file_watcher = FileWatcher(ws.knowledge_dir, indexer)

        _services = AppServices(
            workspace=ws,
            config=config,
            sqlite=sqlite,
            vector_store=vector_store,
            audit=audit,
            model_gateway=model_gateway,
            rag=rag,
            memory=memory,
            skill_loader=skill_loader,
            skill_selector=skill_selector,
            projects=projects,
            permission_checker=permission_checker,
            tool_registry=tool_registry,
            tool_runner=tool_runner,
            skill_installer=skill_installer,
            indexer=indexer,
            agent=agent,
            file_watcher=file_watcher,
        )
        _init_error = None
        _services_ready.set()
        return _services


def bootstrap_services_async() -> None:
    """在后台线程完成服务初始化（供 API lifespan 调用）."""

    def _run() -> None:
        global _init_error
        try:
            services = init_services()
            services.file_watcher.start()
            _services_ready.set()
            logger.info("核心服务初始化完成")
        except Exception as e:
            _init_error = str(e)
            logger.exception("核心服务初始化失败: {}", e)

    if _services_ready.is_set():
        return
    threading.Thread(target=_run, daemon=True, name="services-bootstrap").start()


def is_ready() -> bool:
    return _services_ready.is_set() and _services is not None


def get_services() -> AppServices:
    if _services is not None:
        return _services
    if not _services_ready.wait(timeout=INIT_TIMEOUT_SEC):
        msg = _init_error or "服务初始化超时"
        raise RuntimeError(msg)
    if _services is None:
        raise RuntimeError(_init_error or "服务未就绪")
    return _services


def run_startup_indexing() -> None:
    try:
        services = get_services()
        stats = services.indexer.index_directory()
        logger.info("启动索引完成: {}", stats)
    except Exception as e:
        logger.error("后台索引失败: {}", e)
