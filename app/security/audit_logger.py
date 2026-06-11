"""审计日志."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Column, String, Text, create_engine, desc, select
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config.workspace import Workspace


class AuditBase(DeclarativeBase):
    pass


class AuditLog(AuditBase):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False)
    event_detail = Column(Text)
    created_at = Column(String)


class AuditLogger:
    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self.logs_dir = workspace.logs_dir
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.tool_calls_log = self.logs_dir / "tool_calls.log"
        self.engine = create_engine(f"sqlite:///{workspace.audit_db_path}")
        AuditBase.metadata.create_all(self.engine)
        self._session = sessionmaker(bind=self.engine)

    def log(self, event_type: str, detail: dict[str, Any] | None = None) -> str:
        log_id = f"log_{uuid.uuid4().hex[:12]}"
        with self._session() as session:
            entry = AuditLog(
                id=log_id,
                event_type=event_type,
                event_detail=json.dumps(detail or {}, ensure_ascii=False),
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            session.add(entry)
            session.commit()
        return log_id

    def log_model_call(
        self,
        provider: str,
        model: str,
        *,
        token_input: int = 0,
        token_output: int = 0,
        stream: bool = False,
        conversation_id: str = "",
    ) -> None:
        self.log(
            "model_call",
            {
                "provider": provider,
                "model": model,
                "token_input": token_input,
                "token_output": token_output,
                "stream": stream,
                "conversation_id": conversation_id,
            },
        )

    def log_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        skill_id: str = "",
        result: dict[str, Any] | None = None,
        error: str = "",
        dry_run: bool = False,
    ) -> None:
        detail = {
            "tool_name": tool_name,
            "arguments": arguments,
            "skill_id": skill_id,
            "result": result,
            "error": error,
            "dry_run": dry_run,
        }
        self.log("tool_call", detail)
        self._append_file_log(
            self.tool_calls_log,
            {"event": "tool_call", **detail},
        )

    def log_permission_denied(
        self,
        skill_id: str,
        skill_name: str,
        reasons: list[str],
        permissions: dict[str, Any] | None = None,
    ) -> None:
        self.log(
            "permission_denied",
            {
                "skill_id": skill_id,
                "skill_name": skill_name,
                "reasons": reasons,
                "permissions": permissions or {},
            },
        )

    def log_error(self, source: str, message: str, detail: dict[str, Any] | None = None) -> None:
        self.log(
            "error_exception",
            {"source": source, "message": message, **(detail or {})},
        )

    def query_logs(
        self, event_type: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        with self._session() as session:
            q = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
            if event_type:
                q = q.where(AuditLog.event_type == event_type)
            rows = list(session.execute(q).scalars())
            return [self._row_to_dict(row) for row in rows]

    @staticmethod
    def _row_to_dict(row: AuditLog) -> dict[str, Any]:
        detail: dict[str, Any] = {}
        if row.event_detail:
            try:
                detail = json.loads(row.event_detail)
            except json.JSONDecodeError:
                detail = {"raw": row.event_detail}
        return {
            "id": row.id,
            "event_type": row.event_type,
            "detail": detail,
            "created_at": row.created_at,
        }

    def _append_file_log(self, path: Path, payload: dict[str, Any]) -> None:
        line = json.dumps(
            {"ts": datetime.now(timezone.utc).isoformat(), **payload},
            ensure_ascii=False,
        )
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
