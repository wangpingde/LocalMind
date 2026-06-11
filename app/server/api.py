"""FastAPI 应用."""

from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.server.routes import audit, chat, knowledge, memory, projects, settings, skills, tools
from app.services import bootstrap_services_async, is_ready, run_startup_indexing


@asynccontextmanager
async def lifespan(app: FastAPI):
    bootstrap_services_async()
    threading.Thread(target=run_startup_indexing, daemon=True, name="startup-index").start()
    logger.info("本地 API 进程已启动，核心服务后台加载中")
    yield
    if is_ready():
        from app.services import get_services

        svc = get_services()
        if svc.file_watcher:
            svc.file_watcher.stop()


def create_app() -> FastAPI:
    app = FastAPI(title="LocalMind API", version="0.3.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(chat.router, prefix="/api")
    app.include_router(knowledge.router, prefix="/api")
    app.include_router(memory.router, prefix="/api")
    app.include_router(skills.router, prefix="/api")
    app.include_router(settings.router, prefix="/api")
    app.include_router(projects.router, prefix="/api")
    app.include_router(audit.router, prefix="/api")
    app.include_router(tools.router, prefix="/api")

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        if is_ready():
            try:
                from app.services import get_services

                get_services().audit.log_error(
                    source=f"{request.method} {request.url.path}",
                    message=str(exc),
                )
            except Exception:
                pass
        logger.exception("未处理异常: {}", exc)
        return JSONResponse(status_code=500, content={"detail": str(exc)})

    @app.get("/api/health")
    def health():
        """轻量健康检查，不阻塞等待核心服务."""
        if is_ready():
            from app.services import get_services

            svc = get_services()
            return {
                "status": "ok",
                "ready": True,
                "workspace": str(svc.workspace.root),
            }
        return {"status": "ok", "ready": False, "workspace": ""}

    return app
