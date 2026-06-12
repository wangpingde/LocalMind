"""上下文组装."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.config.app_config import AppSettings
from app.core.memory.memory_manager import MemoryHit
from app.core.rag.retriever import RetrievalResult
from app.core.skills.skill import Skill
from app.core.skills.skill_activator import SkillActivator


@dataclass
class BuiltContext:
    system_prompt: str
    messages: list[dict[str, str]]
    used_skills: list[Skill] = field(default_factory=list)
    used_memories: list[MemoryHit] = field(default_factory=list)
    used_documents: list[RetrievalResult] = field(default_factory=list)


class ContextBuilder:
    SYSTEM_RULES = (
        "你是 LocalMind，一个本地个人 Agent。\n"
        "你必须优先使用本地知识库资料和用户长期记忆。\n"
        "如果本地资料没有明确依据，必须说明「当前本地资料中没有找到明确依据」。\n"
        "不得编造本地文档中不存在的事实。"
    )

    def __init__(self) -> None:
        self._skill_activator = SkillActivator()

    def build(
        self,
        user_input: str,
        history: list[dict[str, str]],
        skills: list[Skill],
        memories: list[MemoryHit],
        rag_results: list[RetrievalResult],
        settings: AppSettings,
        project: dict | None = None,
    ) -> BuiltContext:
        parts = ["# System Rules", self.SYSTEM_RULES]

        if project:
            parts.append("\n# Current Project")
            parts.append(f"项目名称: {project.get('name', '')}")
            if project.get("description"):
                parts.append(f"项目说明: {project['description']}")
            if project.get("knowledge_path"):
                parts.append(f"项目知识库路径: {project['knowledge_path']}")

        if skills:
            parts.append(self._skill_activator.build_sections(skills))

        if memories and settings.send_memory_to_model:
            parts.append("\n# User Memories")
            for mem in memories:
                parts.append(f"- [{mem.type}] {mem.content}")

        if rag_results:
            parts.append("\n# Local Knowledge")
            image_refs = [d for d in rag_results if getattr(d, "media_path", None)]
            if image_refs:
                parts.append(
                    "以下片段含配图（界面会在回答下方自动展示原图）。请用自然语言描述图中内容，"
                    "不要说「见配图路径」或输出 `[配图:...]` 这类标记。"
                )
            for i, doc in enumerate(rag_results, 1):
                source = doc.filename
                if settings.send_file_path_to_model:
                    source = f"{doc.filename} ({doc.path})"
                heading = f" > {doc.heading_path}" if doc.heading_path else ""
                has_image = bool(getattr(doc, "media_path", None))
                image_hint = "\n（含配图，见界面展示）" if has_image else ""
                parts.append(f"## 片段 {i}: {source}{heading}{image_hint}\n{doc.content}")

        system_prompt = "\n".join(parts)
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]

        for msg in history:
            if msg["role"] in ("user", "assistant"):
                messages.append(msg)

        messages.append({"role": "user", "content": user_input})

        return BuiltContext(
            system_prompt=system_prompt,
            messages=messages,
            used_skills=skills,
            used_memories=memories,
            used_documents=rag_results,
        )
