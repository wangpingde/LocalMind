"""审计日志路由."""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.services import get_services

router = APIRouter(tags=["audit"])


@router.get("/audit/logs")
def list_audit_logs(
    event_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    svc = get_services()
    return svc.audit.query_logs(event_type=event_type, limit=limit)


@router.get("/audit/tool-calls")
def list_tool_calls(limit: int = Query(30, ge=1, le=200)):
    svc = get_services()
    return svc.audit.query_logs(event_type="tool_call", limit=limit)
