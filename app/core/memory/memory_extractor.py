"""对话后自动记忆抽取."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.core.llm.model_gateway import ModelGateway
from app.core.llm.reasoning import ChatResult
from app.core.memory.memory_manager import MemoryManager
from app.security.audit_logger import AuditLogger

logger = logging.getLogger(__name__)

VALID_TYPES = frozenset({"profile", "preference", "project", "skill", "episodic", "semantic"})

REMEMBER_HINTS = ("请记住", "记住", "帮我记", "要记得", "别忘了", "保存到记忆")

EXTRACT_SYSTEM = "你是记忆抽取助手。只输出合法 JSON 数组，不要 markdown 或其他文字。"

EXTRACT_USER_TEMPLATE = """分析以下对话，提取值得长期保存的用户记忆。

只提取满足以下条件的稳定信息：
1. 用户明确要求记住
2. 用户身份、职业、角色
3. 长期稳定的偏好和习惯
4. 可复用的工作方法
5. 长期项目背景

不要提取：
1. 一次性任务或临时安排
2. 短暂情绪
3. 敏感隐私（除非用户明确提供且必要）
4. 模型推测未经用户确认的内容
5. 普通问答中无个人信息的句子

用户消息：
{user_input}

助手回复：
{assistant_reply}

已有记忆（避免重复，相似内容不要再提取）：
{existing}

请以 JSON 数组返回，每项格式：
{{"type":"profile|preference|project|skill|episodic|semantic", "content":"简短陈述句", "tags":["..."], "confidence":0.0-1.0}}

若无值得保存的记忆，返回 []。"""


@dataclass
class ExtractedMemory:
    type: str
    content: str
    tags: list[str]
    confidence: float


class MemoryExtractor:
    def __init__(
        self,
        memory: MemoryManager,
        model_gateway: ModelGateway,
        audit: AuditLogger,
        project_id: str | None = None,
    ) -> None:
        self.memory = memory
        self.model_gateway = model_gateway
        self.audit = audit
        self.project_id = project_id

    def extract_and_save(self, user_input: str, assistant_reply: str) -> list[dict[str, Any]]:
        if not user_input.strip() or not assistant_reply.strip():
            return []

        explicit = any(h in user_input for h in REMEMBER_HINTS)
        min_confidence = 0.5 if explicit else 0.7

        existing = self.memory.list_all()
        existing_text = "\n".join(
            f"- [{m.type}] {m.content}" for m in existing[:20] if m.status == "active"
        ) or "（无）"

        prompt = EXTRACT_USER_TEMPLATE.format(
            user_input=user_input[:2000],
            assistant_reply=assistant_reply[:2000],
            existing=existing_text,
        )

        try:
            result = self.model_gateway.chat(
                [
                    {"role": "system", "content": EXTRACT_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                stream=False,
            )
            if not isinstance(result, ChatResult):
                return []
            raw = result.content.strip()
        except Exception:
            logger.exception("memory extraction LLM call failed")
            return []

        candidates = parse_extraction_response(raw)
        saved: list[dict[str, Any]] = []

        for candidate in candidates:
            if candidate.confidence < min_confidence:
                continue
            memory_type = (
                candidate.type if candidate.type in VALID_TYPES else "semantic"
            )

            similar = self.memory.find_similar(candidate.content)
            if similar:
                mem = self.memory.upsert_memory(
                    memory_type,
                    candidate.content,
                    tags=candidate.tags,
                    memory_id=similar.id,
                    confidence=max(similar.confidence or 0, candidate.confidence),
                    project_id=self.project_id or similar.project_id,
                )
                action = "merged"
            else:
                mem_type = memory_type
                if self.project_id and memory_type == "semantic":
                    mem_type = "project"
                mem = self.memory.upsert_memory(
                    mem_type,
                    candidate.content,
                    tags=candidate.tags,
                    source="auto",
                    confidence=candidate.confidence,
                    project_id=self.project_id,
                )
                action = "created"

            saved.append({**self.memory.memory_to_dict(mem), "action": action})
            self.audit.log(
                "memory_auto_saved",
                {
                    "memory_id": mem.id,
                    "type": mem.type,
                    "action": action,
                    "confidence": candidate.confidence,
                },
            )

        if saved:
            logger.info("auto-saved %d memories from chat", len(saved))
        return saved


def parse_extraction_response(raw: str) -> list[ExtractedMemory]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if not match:
            logger.warning("failed to parse memory extraction: %s", raw[:200])
            return []
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            return []

    if not isinstance(data, list):
        return []

    candidates: list[ExtractedMemory] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content", "")).strip()
        if len(content) < 4:
            continue
        try:
            confidence = float(item.get("confidence", 0.8))
        except (TypeError, ValueError):
            confidence = 0.8
        candidates.append(
            ExtractedMemory(
                type=str(item.get("type", "semantic")),
                content=content,
                tags=[str(t) for t in (item.get("tags") or [])],
                confidence=confidence,
            )
        )
    return candidates
