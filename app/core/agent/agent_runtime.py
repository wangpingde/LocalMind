"""Agent 运行时."""

from __future__ import annotations

import logging
import threading
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

from app.config.app_config import ConfigManager
from app.core.agent.agent_orchestrator import AgentOrchestrator
from app.core.agent.context_builder import ContextBuilder
from app.core.llm.model_gateway import ModelGateway
from app.core.llm.reasoning import ChatResult, StreamPart, serialize_assistant_message
from app.core.memory.memory_manager import MemoryManager
from app.core.project.project_manager import ProjectManager
from app.core.rag.retriever import RAGEngine
from app.core.skills.skill_selector import SkillSelector
from app.core.tools.registry import ToolRegistry
from app.core.tools.tool_runner import ToolRunner
from app.security.audit_logger import AuditLogger
from app.storage.sqlite_store import SQLiteStore


@dataclass
class AgentResponse:
    content: str
    reasoning: str = ""
    message_id: str = ""
    conversation_id: str = ""
    used_memories: list[dict[str, Any]] = field(default_factory=list)
    used_documents: list[dict[str, Any]] = field(default_factory=list)
    used_skills: list[dict[str, Any]] = field(default_factory=list)
    retrieval_chunks: list[dict[str, Any]] = field(default_factory=list)
    token_usage: dict[str, int] = field(default_factory=dict)
    agent_steps: list[dict[str, Any]] = field(default_factory=list)
    agent_run_id: str = ""


class AgentRuntime:
    def __init__(
        self,
        config: ConfigManager,
        model_gateway: ModelGateway,
        rag: RAGEngine,
        memory: MemoryManager,
        skill_selector: SkillSelector,
        sqlite: SQLiteStore,
        audit: AuditLogger,
        projects: ProjectManager,
        tool_runner: ToolRunner,
        tool_registry: ToolRegistry,
    ) -> None:
        self.config = config
        self.model_gateway = model_gateway
        self.rag = rag
        self.memory = memory
        self.skill_selector = skill_selector
        self.sqlite = sqlite
        self.audit = audit
        self.projects = projects
        self.tool_runner = tool_runner
        self.tool_registry = tool_registry
        self.context_builder = ContextBuilder()
        self.orchestrator = AgentOrchestrator(model_gateway, tool_runner, sqlite)
        self._current_project_id: str | None = None

    def run(
        self,
        user_input: str,
        conversation_id: str | None = None,
        model: str | None = None,
        stream: bool = False,
        project_id: str | None = None,
    ) -> AgentResponse | Generator[dict[str, Any], None, None]:
        settings = self.config.load_settings()
        self._current_project_id = project_id

        if not conversation_id:
            conv = self.sqlite.create_conversation(title=user_input[:30])
            conversation_id = conv.id

        self.sqlite.add_message(conversation_id, "user", user_input)

        project_info = None
        path_prefix = None
        if project_id:
            project = self.projects.get_project(project_id)
            if project:
                project_info = project.to_dict()
                path_prefix = self.projects.path_prefix(project_id)

        skills = self.skill_selector.select(user_input, settings)
        memories = self.memory.search(user_input, project_id=project_id)
        rag_resp = self.rag.retrieve(user_input, top_k=8, path_prefix=path_prefix)

        from app.core.llm.reasoning import parse_assistant_message

        history = []
        for m in self.sqlite.get_messages(conversation_id, limit=20):
            if m.role not in ("user", "assistant"):
                continue
            content = m.content
            if m.role == "assistant":
                _, answer, _ = parse_assistant_message(m.content)
                content = answer or m.content
            history.append({"role": m.role, "content": content})
        history = history[:-1]

        ctx = self.context_builder.build(
            user_input=user_input,
            history=history,
            skills=skills,
            memories=memories,
            rag_results=rag_resp.results,
            settings=settings,
            project=project_info,
        )

        provider_name, provider = self.model_gateway.get_provider(model)
        use_tools = (
            settings.tools_enabled
            and self.model_gateway.supports_tools(model)
        )

        if use_tools:
            if stream:
                return self._run_stream_with_tools(
                    ctx,
                    conversation_id,
                    provider_name,
                    provider.chat_model,
                    user_input,
                    settings=settings,
                    skills=skills,
                    path_prefix=path_prefix,
                )
            loop_result = self.orchestrator.run_loop(
                ctx.messages,
                conversation_id=conversation_id,
                user_input=user_input,
                settings=settings,
                skills=skills,
                project_path_prefix=path_prefix,
                provider_name=provider_name,
                tool_schemas=self.tool_registry.openai_schemas_for(skills),
            )
            return self._finalize(
                loop_result.content,
                conversation_id,
                ctx,
                provider.chat_model,
                user_input,
                reasoning=loop_result.reasoning,
                agent_steps=[{"step_type": s.step_type, **s.content} for s in loop_result.steps],
                agent_run_id=loop_result.run_id,
            )

        if stream:
            return self._run_stream(
                ctx,
                conversation_id,
                provider_name,
                provider.chat_model,
                user_input,
            )

        result = self.model_gateway.chat(ctx.messages, stream=False, provider_name=model)
        if isinstance(result, ChatResult):
            return self._finalize(
                result.content,
                conversation_id,
                ctx,
                provider.chat_model,
                user_input,
                reasoning=result.reasoning,
            )
        return AgentResponse(content="")

    def _run_stream_with_tools(
        self,
        ctx,
        conversation_id: str,
        provider_name: str,
        model_name: str,
        user_input: str,
        *,
        settings,
        skills,
        path_prefix: str | None,
    ) -> Generator[dict[str, Any], None, None]:
        loop_result = None

        for event in self.orchestrator.iter_loop(
            ctx.messages,
            conversation_id=conversation_id,
            user_input=user_input,
            settings=settings,
            skills=skills,
            project_path_prefix=path_prefix,
            provider_name=provider_name,
            tool_schemas=self.tool_registry.openai_schemas_for(skills),
        ):
            etype = event.get("type")
            if etype in ("step_delta", "answer_reset", "chunk", "step"):
                yield event
            elif etype == "complete":
                loop_result = event["result"]

        if loop_result is None:
            loop_result = type(
                "R", (), {"content": "", "reasoning": "", "steps": [], "run_id": ""}
            )()

        content = loop_result.content
        reasoning = loop_result.reasoning
        agent_steps = [
            {"step_type": s.step_type, **s.content} for s in loop_result.steps
        ]

        resp = self._finalize(
            content,
            conversation_id,
            ctx,
            model_name,
            user_input,
            reasoning=reasoning,
            agent_steps=agent_steps,
            agent_run_id=loop_result.run_id,
        )
        yield {"type": "done", **self.response_to_dict(resp)}

    def _run_stream(
        self,
        ctx,
        conversation_id,
        provider_name,
        model_name,
        user_input,
    ) -> Generator[dict[str, Any], None, None]:
        stream = self.model_gateway.chat(
            ctx.messages, stream=True, provider_name=provider_name
        )
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        if hasattr(stream, "__iter__"):
            for part in stream:
                if not isinstance(part, StreamPart):
                    continue
                if part.kind == "reasoning" and part.text:
                    reasoning_parts.append(part.text)
                    yield {"type": "reasoning", "content": part.text}
                elif part.kind == "content" and part.text:
                    content_parts.append(part.text)
                    yield {"type": "chunk", "content": part.text}
        content = "".join(content_parts)
        reasoning = "".join(reasoning_parts)
        resp = self._finalize(
            content, conversation_id, ctx, model_name, user_input, reasoning=reasoning
        )
        yield {"type": "done", **self.response_to_dict(resp)}

    def _finalize(
        self,
        content: str,
        conversation_id: str,
        ctx,
        model_name: str,
        user_input: str,
        reasoning: str = "",
        agent_steps: list[dict[str, Any]] | None = None,
        agent_run_id: str = "",
    ) -> AgentResponse:
        stored = serialize_assistant_message(
            content, reasoning, agent_steps=agent_steps or None
        )
        msg = self.sqlite.add_message(
            conversation_id,
            "assistant",
            stored,
            model_name=model_name,
            token_input=len(ctx.system_prompt) // 4 + len(user_input) // 4,
            token_output=(len(content) + len(reasoning)) // 4,
        )

        self.audit.log(
            "chat_completed",
            {
                "conversation_id": conversation_id,
                "project_id": self._current_project_id,
                "skills": [s.id for s in ctx.used_skills],
                "memories": [m.id for m in ctx.used_memories],
                "documents": [d.filename for d in ctx.used_documents],
                "has_reasoning": bool(reasoning),
                "agent_run_id": agent_run_id,
                "agent_steps": len(agent_steps or []),
            },
        )
        self.audit.log_model_call(
            provider=model_name,
            model=model_name,
            token_input=msg.token_input or 0,
            token_output=msg.token_output or 0,
            conversation_id=conversation_id,
        )

        settings = self.config.load_settings()
        if settings.auto_memory_enabled:
            threading.Thread(
                target=self._extract_memories_bg,
                args=(user_input, content, self._current_project_id),
                daemon=True,
                name="memory-extract",
            ).start()

        return AgentResponse(
            content=content,
            reasoning=reasoning,
            message_id=msg.id,
            conversation_id=conversation_id,
            used_memories=[
                {"id": m.id, "type": m.type, "content": m.content, "score": m.score}
                for m in ctx.used_memories
            ],
            used_documents=[
                {
                    "filename": d.filename,
                    "path": d.path,
                    "heading_path": d.heading_path,
                    "score": d.score,
                }
                for d in ctx.used_documents
            ],
            used_skills=[
                self._skill_present_dict(s, settings)
                for s in ctx.used_skills
            ],
            retrieval_chunks=self.rag.to_dict(
                type("R", (), {"query": user_input, "results": ctx.used_documents})()
            )["results"],
            token_usage={
                "input": msg.token_input or 0,
                "output": msg.token_output or 0,
            },
            agent_steps=agent_steps or [],
            agent_run_id=agent_run_id,
        )

    def _skill_present_dict(self, skill, settings) -> dict[str, Any]:
        from app.core.skills.skill_presenter import enrich_skill_dict

        return enrich_skill_dict(
            skill, self.tool_runner.permission_checker, settings
        )

    def _extract_memories_bg(
        self, user_input: str, assistant_reply: str, project_id: str | None
    ) -> None:
        try:
            from app.core.memory.memory_extractor import MemoryExtractor

            extractor = MemoryExtractor(
                self.memory, self.model_gateway, self.audit, project_id=project_id
            )
            extractor.extract_and_save(user_input, assistant_reply)
        except Exception:
            logger.exception("background memory extraction failed")

    def response_to_dict(self, resp: AgentResponse) -> dict[str, Any]:
        return {
            "message_id": resp.message_id,
            "content": resp.content,
            "reasoning": resp.reasoning,
            "conversation_id": resp.conversation_id,
            "project_id": self._current_project_id,
            "used_memories": resp.used_memories,
            "used_documents": resp.used_documents,
            "used_skills": resp.used_skills,
            "retrieval_chunks": resp.retrieval_chunks,
            "token_usage": resp.token_usage,
            "agent_steps": resp.agent_steps,
            "agent_run_id": resp.agent_run_id,
        }
