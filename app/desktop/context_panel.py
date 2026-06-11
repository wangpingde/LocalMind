"""右侧上下文透明区."""

from __future__ import annotations

import json

from PySide6.QtWidgets import QLabel, QTabWidget, QTextEdit, QVBoxLayout, QWidget

from app.core.skills.skill_presenter import format_used_skills_context
from app.desktop.api_client import ApiClient


class ContextPanel(QWidget):
    def __init__(self, client: ApiClient | None = None) -> None:
        super().__init__()
        self.client = client
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 16)
        layout.setSpacing(10)

        title = QLabel("上下文")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        subtitle = QLabel("本次回答引用的资料与能力")
        subtitle.setObjectName("panelSubtitle")
        layout.addWidget(subtitle)

        layout.addSpacing(4)

        self.tabs = QTabWidget()
        self.docs_view = self._make_view()
        self.memories_view = self._make_view()
        self.skills_view = self._make_view()
        self.chunks_view = self._make_view()
        self.steps_view = self._make_view()
        self.audit_view = self._make_view()
        self.usage_view = self._make_view()

        self.tabs.addTab(self.docs_view, "文档")
        self.tabs.addTab(self.memories_view, "记忆")
        self.tabs.addTab(self.skills_view, "Skills")
        self.tabs.addTab(self.chunks_view, "检索")
        self.tabs.addTab(self.steps_view, "步骤")
        self.tabs.addTab(self.audit_view, "审计")
        self.tabs.addTab(self.usage_view, "消耗")
        layout.addWidget(self.tabs)

    @staticmethod
    def _make_view() -> QTextEdit:
        view = QTextEdit()
        view.setObjectName("contextView")
        view.setReadOnly(True)
        return view

    def update_context(self, data: dict) -> None:
        docs = data.get("used_documents", [])
        chunks = data.get("retrieval_chunks", [])
        project_id = data.get("project_id")
        doc_lines = [
            f"▸ {d.get('filename', '')}  ({d.get('score', 0):.2f})" for d in docs
        ]
        if not doc_lines and chunks:
            doc_lines = [
                f"▸ {c.get('filename', '')}  ({c.get('score', 0):.2f})" for c in chunks
            ]
        if project_id and not doc_lines:
            doc_lines = [
                "当前已选项目，但未检索到该项目知识库中的文档。",
                "请将文档放入 knowledge/projects/<项目>/ 并重新索引。",
            ]
        self.docs_view.setPlainText("\n".join(doc_lines) or "未使用本地文档")

        memories = data.get("used_memories", [])
        self.memories_view.setPlainText(
            "\n".join(f"▸ [{m.get('type')}] {m.get('content', '')}" for m in memories)
            or "未使用记忆"
        )

        skills = data.get("used_skills", [])
        agent_steps = data.get("agent_steps", [])
        self.skills_view.setPlainText(
            format_used_skills_context(skills, agent_steps)
        )

        chunks = data.get("retrieval_chunks", [])
        chunk_parts = []
        for i, c in enumerate(chunks, 1):
            chunk_parts.append(f"── 片段 {i}: {c.get('filename', '')} ──")
            chunk_parts.append(c.get("content", "")[:500])
        self.chunks_view.setPlainText("\n\n".join(chunk_parts) or "无检索片段")

        agent_steps = data.get("agent_steps", [])
        step_parts: list[str] = []
        for i, step in enumerate(agent_steps, 1):
            stype = step.get("step_type", "")
            if stype == "tool_call":
                step_parts.append(
                    f"步骤 {i} ▸ 调用 {step.get('tool', '')}\n"
                    f"  参数: {json.dumps(step.get('arguments', {}), ensure_ascii=False)}"
                )
            elif stype == "tool_result":
                result = step.get("result", {})
                summary = result.get("message") or result.get("status", "")
                if result.get("succeeded") is not None:
                    summary = (
                        f"成功 {result.get('succeeded')} / 共 {result.get('total', 0)}"
                    )
                step_parts.append(f"步骤 {i} ▸ 结果 {step.get('tool', '')}: {summary}")
            elif stype == "reasoning":
                step_parts.append(f"步骤 {i} ▸ 思考\n  {step.get('text', '')[:300]}")
            else:
                step_parts.append(f"步骤 {i} ▸ {stype}\n  {step.get('text', '')[:300]}")
        self.steps_view.setPlainText("\n\n".join(step_parts) or "无 Agent 执行步骤")

        usage = data.get("token_usage", {})
        reasoning = data.get("reasoning", "")
        lines = [
            f"输入  {usage.get('input', 0)} tokens",
            f"输出  {usage.get('output', 0)} tokens",
        ]
        if reasoning:
            lines.append(f"思考  {len(reasoning)} 字符")
        self.usage_view.setPlainText("\n".join(lines))

        self._load_audit_logs()

    @staticmethod
    def _format_audit_detail(event_type: str, detail: dict) -> str:
        """按事件类型格式化审计详情，完整展示不截断。"""
        if event_type == "tool_call":
            parts = [detail.get("tool_name", "")]
            if detail.get("skill_id"):
                parts.append(f"skill={detail['skill_id']}")
            if detail.get("dry_run"):
                parts.append("dry_run")
            if detail.get("error"):
                parts.append(f"error={detail['error']}")
            return " | ".join(p for p in parts if p)

        if event_type == "model_call":
            return (
                f"model={detail.get('model', '')}  "
                f"in={detail.get('token_input', 0)}  "
                f"out={detail.get('token_output', 0)}  "
                f"stream={detail.get('stream', False)}"
            )

        if event_type == "chat_completed":
            lines: list[str] = []
            if detail.get("conversation_id"):
                lines.append(f"对话: {detail['conversation_id']}")
            if detail.get("project_id"):
                lines.append(f"项目: {detail['project_id']}")
            skills = detail.get("skills") or []
            lines.append(f"Skills: {', '.join(skills) if skills else '无'}")
            memories = detail.get("memories") or []
            lines.append(f"记忆: {', '.join(memories) if memories else '无'}")
            documents = detail.get("documents") or []
            lines.append(f"文档: {', '.join(documents) if documents else '无'}")
            if detail.get("has_reasoning"):
                lines.append("含思考过程: 是")
            return "\n".join(lines)

        if event_type == "permission_denied":
            reasons = detail.get("reasons") or []
            return (
                f"{detail.get('skill_name', detail.get('skill_id', ''))}  "
                f"拒绝: {'; '.join(reasons)}"
            )

        if detail.get("message"):
            return str(detail["message"])

        if not detail:
            return ""

        return json.dumps(detail, ensure_ascii=False, indent=2)

    def _load_audit_logs(self) -> None:
        if not self.client:
            self.audit_view.setPlainText("审计日志不可用")
            return
        try:
            logs = self.client.get("/audit/logs?limit=20")
            blocks: list[str] = []
            for entry in logs:
                detail = entry.get("detail", {})
                if isinstance(detail, str):
                    try:
                        detail = json.loads(detail)
                    except json.JSONDecodeError:
                        detail = {"raw": detail}
                if not isinstance(detail, dict):
                    detail = {"raw": detail}

                event_type = entry.get("event_type", "")
                created = (entry.get("created_at") or "")[:19]
                body = self._format_audit_detail(event_type, detail)
                if "\n" in body:
                    blocks.append(f"{created}  [{event_type}]\n{body}")
                else:
                    blocks.append(f"{created}  [{event_type}]  {body}")
            self.audit_view.setPlainText("\n\n".join(blocks) or "暂无审计记录")
        except Exception as e:
            self.audit_view.setPlainText(f"加载审计失败: {e}")

    def clear(self) -> None:
        for view in (
            self.docs_view,
            self.memories_view,
            self.skills_view,
            self.chunks_view,
            self.steps_view,
            self.audit_view,
            self.usage_view,
        ):
            view.clear()
