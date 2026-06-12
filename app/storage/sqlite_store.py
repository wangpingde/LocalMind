"""SQLite 数据存储."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import (
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config.workspace import Workspace


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    path = Column(String, nullable=False)
    filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    size = Column(Integer)
    sha256 = Column(String)
    created_at = Column(String)
    updated_at = Column(String)
    indexed_at = Column(String)
    status = Column(String, default="pending")
    error_message = Column(Text)


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(String, primary_key=True)
    document_id = Column(String, ForeignKey("documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(Text)
    tags = Column(Text)
    page_no = Column(Integer)
    heading_path = Column(String)
    token_count = Column(Integer)
    created_at = Column(String)


class Memory(Base):
    __tablename__ = "memories"

    id = Column(String, primary_key=True)
    type = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    source = Column(String, default="manual")
    confidence = Column(Float, default=1.0)
    status = Column(String, default="active")
    version = Column(Integer, default=1)
    created_at = Column(String)
    updated_at = Column(String)
    last_used_at = Column(String)
    tags = Column(Text)
    project_id = Column(String)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True)
    title = Column(String)
    created_at = Column(String)
    updated_at = Column(String)


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(String)
    model_name = Column(String)
    token_input = Column(Integer)
    token_output = Column(Integer)


class Project(Base):
    __tablename__ = "projects"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    slug = Column(String, nullable=False)
    knowledge_path = Column(String)
    status = Column(String, default="active")
    created_at = Column(String)
    updated_at = Column(String)


class SkillRecord(Base):
    __tablename__ = "skills"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    version = Column(String)
    description = Column(Text)
    path = Column(String, nullable=False)
    enabled = Column(Integer, default=1)
    installed_at = Column(String)
    updated_at = Column(String)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(String, primary_key=True)
    conversation_id = Column(String, ForeignKey("conversations.id"))
    user_input = Column(Text)
    status = Column(String, default="running")
    step_count = Column(Integer, default=0)
    created_at = Column(String)
    updated_at = Column(String)


class AgentRunStep(Base):
    __tablename__ = "agent_run_steps"

    id = Column(String, primary_key=True)
    run_id = Column(String, ForeignKey("agent_runs.id"), nullable=False)
    step_index = Column(Integer, nullable=False)
    step_type = Column(String, nullable=False)
    content = Column(Text)
    created_at = Column(String)


class SQLiteStore:
    def __init__(self, workspace: Workspace) -> None:
        self.engine = create_engine(f"sqlite:///{workspace.db_path}")
        Base.metadata.create_all(self.engine)
        self._session = sessionmaker(bind=self.engine)

    def session(self) -> Session:
        return self._session()

    # --- Documents ---

    def upsert_document(self, **kwargs: Any) -> Document:
        with self.session() as s:
            doc_id = kwargs.pop("id", None) or _new_id("doc")
            existing = s.get(Document, doc_id)
            now = _now()
            if existing:
                for k, v in kwargs.items():
                    if v is not None:
                        setattr(existing, k, v)
                existing.updated_at = now
                s.commit()
                s.refresh(existing)
                return existing
            doc = Document(id=doc_id, created_at=now, updated_at=now, **kwargs)
            s.add(doc)
            s.commit()
            s.refresh(doc)
            return doc

    def get_document_by_path(self, path: str) -> Document | None:
        with self.session() as s:
            return s.execute(select(Document).where(Document.path == path)).scalar_one_or_none()

    def get_document(self, document_id: str) -> Document | None:
        with self.session() as s:
            return s.get(Document, document_id)

    def get_chunk(self, chunk_id: str) -> Chunk | None:
        with self.session() as s:
            return s.get(Chunk, chunk_id)

    def list_documents(self) -> list[Document]:
        with self.session() as s:
            return list(s.execute(select(Document).order_by(Document.updated_at.desc())).scalars())

    def count_document_chunks(self, document_id: str) -> int:
        with self.session() as s:
            chunks = s.execute(select(Chunk).where(Chunk.document_id == document_id)).scalars()
            return len(list(chunks))

    def document_has_media_description(self, document_id: str) -> bool:
        with self.session() as s:
            chunks = s.execute(select(Chunk).where(Chunk.document_id == document_id)).scalars()
            for chunk in chunks:
                tags = chunk.tags or ""
                content = chunk.content or ""
                if tags in ("media:image", "media:video"):
                    return True
                if "[图片描述]" in content or "[视频画面]" in content:
                    return True
            return False

    def list_chunk_ids(self, document_id: str) -> list[str]:
        with self.session() as s:
            return list(
                s.execute(select(Chunk.id).where(Chunk.document_id == document_id)).scalars()
            )

    def delete_document_chunks(self, document_id: str) -> None:
        with self.session() as s:
            chunks = s.execute(select(Chunk).where(Chunk.document_id == document_id)).scalars()
            for c in chunks:
                s.delete(c)
            s.commit()

    def delete_document(self, document_id: str) -> bool:
        with self.session() as s:
            doc = s.get(Document, document_id)
            if not doc:
                return False
            chunks = s.execute(select(Chunk).where(Chunk.document_id == document_id)).scalars()
            for c in chunks:
                s.delete(c)
            s.delete(doc)
            s.commit()
            return True

    def add_chunks(self, chunks: list[dict[str, Any]]) -> None:
        with self.session() as s:
            for data in chunks:
                chunk = Chunk(created_at=_now(), **data)
                s.add(chunk)
            s.commit()

    def clear_all_documents(self) -> None:
        with self.session() as s:
            s.query(Chunk).delete()
            s.query(Document).delete()
            s.commit()

    # --- Memories ---

    def list_memories(self, memory_type: str | None = None, keyword: str | None = None) -> list[Memory]:
        with self.session() as s:
            q = select(Memory).where(Memory.status != "deleted")
            if memory_type:
                q = q.where(Memory.type == memory_type)
            rows = list(s.execute(q.order_by(Memory.updated_at.desc())).scalars())
            if keyword:
                kw = keyword.lower()
                rows = [m for m in rows if kw in m.content.lower()]
            return rows

    def get_memory(self, memory_id: str) -> Memory | None:
        with self.session() as s:
            return s.get(Memory, memory_id)

    def create_memory(
        self,
        memory_type: str,
        content: str,
        tags: list[str] | None = None,
        source: str = "manual",
        confidence: float = 1.0,
        project_id: str | None = None,
    ) -> Memory:
        now = _now()
        mem = Memory(
            id=_new_id("mem"),
            type=memory_type,
            content=content,
            source=source,
            confidence=confidence,
            status="active",
            version=1,
            created_at=now,
            updated_at=now,
            tags=json.dumps(tags or [], ensure_ascii=False),
            project_id=project_id,
        )
        with self.session() as s:
            s.add(mem)
            s.commit()
            s.refresh(mem)
            return mem

    def update_memory(self, memory_id: str, **kwargs: Any) -> Memory | None:
        with self.session() as s:
            mem = s.get(Memory, memory_id)
            if not mem:
                return None
            for k, v in kwargs.items():
                if v is not None:
                    if k == "tags" and isinstance(v, list):
                        setattr(mem, k, json.dumps(v, ensure_ascii=False))
                    else:
                        setattr(mem, k, v)
            mem.updated_at = _now()
            mem.version = (mem.version or 1) + 1
            s.commit()
            s.refresh(mem)
            return mem

    def delete_memory(self, memory_id: str) -> bool:
        with self.session() as s:
            mem = s.get(Memory, memory_id)
            if not mem:
                return False
            s.delete(mem)
            s.commit()
            return True

    def touch_memory(self, memory_id: str) -> None:
        with self.session() as s:
            mem = s.get(Memory, memory_id)
            if mem:
                mem.last_used_at = _now()
                s.commit()

    # --- Projects ---

    def list_projects(self, active_only: bool = True) -> list[Project]:
        with self.session() as s:
            q = select(Project)
            if active_only:
                q = q.where(Project.status == "active")
            return list(s.execute(q.order_by(Project.updated_at.desc())).scalars())

    def get_project(self, project_id: str) -> Project | None:
        with self.session() as s:
            return s.get(Project, project_id)

    def get_project_by_slug(self, slug: str) -> Project | None:
        with self.session() as s:
            return s.execute(select(Project).where(Project.slug == slug)).scalar_one_or_none()

    def create_project(
        self,
        name: str,
        slug: str,
        description: str = "",
        knowledge_path: str = "",
    ) -> Project:
        now = _now()
        project = Project(
            id=_new_id("proj"),
            name=name,
            description=description,
            slug=slug,
            knowledge_path=knowledge_path,
            status="active",
            created_at=now,
            updated_at=now,
        )
        with self.session() as s:
            s.add(project)
            s.commit()
            s.refresh(project)
            return project

    def update_project(self, project_id: str, **kwargs: Any) -> Project | None:
        with self.session() as s:
            project = s.get(Project, project_id)
            if not project:
                return None
            for k, v in kwargs.items():
                if v is not None:
                    setattr(project, k, v)
            project.updated_at = _now()
            s.commit()
            s.refresh(project)
            return project

    def delete_project(self, project_id: str) -> bool:
        with self.session() as s:
            project = s.get(Project, project_id)
            if not project:
                return False
            s.delete(project)
            s.commit()
            return True

    # --- Conversations ---

    def create_conversation(self, title: str = "新对话") -> Conversation:
        now = _now()
        conv = Conversation(id=_new_id("conv"), title=title, created_at=now, updated_at=now)
        with self.session() as s:
            s.add(conv)
            s.commit()
            s.refresh(conv)
            return conv

    @staticmethod
    def _timestamp_local_date(iso_ts: str | None) -> date | None:
        if not iso_ts:
            return None
        try:
            dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().date()

    def list_conversations(
        self,
        *,
        scope: str = "today",
        keyword: str | None = None,
        today_only: bool | None = None,
    ) -> list[Conversation]:
        """scope: today | week | month | all"""
        if today_only is not None:
            scope = "today" if today_only else "all"

        with self.session() as s:
            rows = list(
                s.execute(select(Conversation).order_by(Conversation.updated_at.desc())).scalars()
            )

        now_local = datetime.now().astimezone()
        today = now_local.date()
        kw = (keyword or "").strip().lower()

        filtered: list[Conversation] = []
        for conv in rows:
            ts = conv.updated_at or conv.created_at
            local_date = self._timestamp_local_date(ts)
            if scope == "today":
                if local_date != today:
                    continue
            elif scope == "week":
                if local_date is None or local_date < today - timedelta(days=6):
                    continue
            elif scope == "month":
                if local_date is None or local_date < today - timedelta(days=29):
                    continue
            elif scope != "all":
                continue

            if kw:
                title = (conv.title or "").lower()
                if kw not in title:
                    continue
            filtered.append(conv)
        return filtered

    def get_conversation(self, conv_id: str) -> Conversation | None:
        with self.session() as s:
            return s.get(Conversation, conv_id)

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        model_name: str | None = None,
        token_input: int | None = None,
        token_output: int | None = None,
    ) -> Message:
        now = _now()
        msg = Message(
            id=_new_id("msg"),
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=now,
            model_name=model_name,
            token_input=token_input,
            token_output=token_output,
        )
        with self.session() as s:
            s.add(msg)
            conv = s.get(Conversation, conversation_id)
            if conv:
                conv.updated_at = now
            s.commit()
            s.refresh(msg)
            return msg

    def get_messages(self, conversation_id: str, limit: int = 50) -> list[Message]:
        with self.session() as s:
            rows = list(
                s.execute(
                    select(Message)
                    .where(Message.conversation_id == conversation_id)
                    .order_by(Message.created_at)
                ).scalars()
            )
            return rows[-limit:]

    def list_agent_run_ids(self, conversation_id: str) -> list[str]:
        with self.session() as s:
            return list(
                s.execute(
                    select(AgentRun.id).where(AgentRun.conversation_id == conversation_id)
                ).scalars()
            )

    def delete_conversation(self, conversation_id: str) -> bool:
        """物理删除会话及其消息、Agent 运行记录."""
        with self.session() as s:
            conv = s.get(Conversation, conversation_id)
            if not conv:
                return False

            runs = list(
                s.execute(
                    select(AgentRun).where(AgentRun.conversation_id == conversation_id)
                ).scalars()
            )
            for run in runs:
                steps = list(
                    s.execute(
                        select(AgentRunStep).where(AgentRunStep.run_id == run.id)
                    ).scalars()
                )
                for step in steps:
                    s.delete(step)
                s.delete(run)

            messages = list(
                s.execute(
                    select(Message).where(Message.conversation_id == conversation_id)
                ).scalars()
            )
            for msg in messages:
                s.delete(msg)

            s.delete(conv)
            s.commit()
            return True

    # --- Skills ---

    def upsert_skill(self, **kwargs: Any) -> SkillRecord:
        with self.session() as s:
            skill_id = kwargs["id"]
            existing = s.get(SkillRecord, skill_id)
            now = _now()
            if existing:
                for k, v in kwargs.items():
                    if v is not None:
                        setattr(existing, k, v)
                existing.updated_at = now
                s.commit()
                s.refresh(existing)
                return existing
            skill = SkillRecord(installed_at=now, updated_at=now, **kwargs)
            s.add(skill)
            s.commit()
            s.refresh(skill)
            return skill

    def list_skills(self) -> list[SkillRecord]:
        with self.session() as s:
            return list(s.execute(select(SkillRecord).order_by(SkillRecord.name)).scalars())

    def set_skill_enabled(self, skill_id: str, enabled: bool) -> SkillRecord | None:
        with self.session() as s:
            skill = s.get(SkillRecord, skill_id)
            if not skill:
                return None
            skill.enabled = 1 if enabled else 0
            skill.updated_at = _now()
            s.commit()
            s.refresh(skill)
            return skill

    # --- Agent runs ---

    def create_agent_run(self, conversation_id: str, user_input: str) -> AgentRun:
        now = _now()
        run = AgentRun(
            id=_new_id("run"),
            conversation_id=conversation_id,
            user_input=user_input,
            status="running",
            step_count=0,
            created_at=now,
            updated_at=now,
        )
        with self.session() as s:
            s.add(run)
            s.commit()
            s.refresh(run)
            return run

    def add_agent_step(
        self, run_id: str, step_index: int, step_type: str, content: dict[str, Any]
    ) -> AgentRunStep:
        now = _now()
        step = AgentRunStep(
            id=_new_id("step"),
            run_id=run_id,
            step_index=step_index,
            step_type=step_type,
            content=json.dumps(content, ensure_ascii=False),
            created_at=now,
        )
        with self.session() as s:
            s.add(step)
            run = s.get(AgentRun, run_id)
            if run:
                run.step_count = step_index + 1
                run.updated_at = now
            s.commit()
            s.refresh(step)
            return step

    def finish_agent_run(self, run_id: str, status: str = "completed") -> None:
        with self.session() as s:
            run = s.get(AgentRun, run_id)
            if run:
                run.status = status
                run.updated_at = _now()
                s.commit()

    def list_agent_steps(self, run_id: str) -> list[AgentRunStep]:
        with self.session() as s:
            return list(
                s.execute(
                    select(AgentRunStep)
                    .where(AgentRunStep.run_id == run_id)
                    .order_by(AgentRunStep.step_index)
                ).scalars()
            )
