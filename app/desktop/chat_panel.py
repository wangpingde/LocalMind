"""聊天面板."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.llm.reasoning import parse_assistant_message
from app.desktop.agent_step_renderer import render_agent_steps_html
from app.desktop.api_client import ApiClient
from app.desktop.message_renderer import render_message_body
from app.desktop.theme import ACCENT, AGENT_MSG, BG_CARD, DANGER, TEXT_MUTED, USER_MSG

REASONING_COLOR = "#8b7ec8"
SCROLL_EDGE_PX = 32
STREAM_RENDER_MS = 32


class ChatWorker(QThread):
    chunk_received = Signal(str)
    reasoning_received = Signal(str)
    step_received = Signal(dict)
    step_delta_received = Signal(dict)
    answer_reset = Signal()
    finished_ok = Signal(dict)
    error = Signal(str)

    def __init__(
        self,
        client: ApiClient,
        message: str,
        conversation_id: str | None,
        model: str | None,
        project_id: str | None,
    ) -> None:
        super().__init__()
        self.client = client
        self.message = message
        self.conversation_id = conversation_id
        self.model = model
        self.project_id = project_id

    def run(self) -> None:
        try:
            for event_type, content, done in self.client.chat_stream(
                self.message, self.conversation_id, self.model, self.project_id
            ):
                if event_type == "reasoning" and content:
                    self.reasoning_received.emit(content)
                elif event_type == "chunk" and content:
                    self.chunk_received.emit(content)
                elif event_type == "step" and content:
                    import json

                    self.step_received.emit(json.loads(content))
                elif event_type == "step_delta" and content:
                    import json

                    self.step_delta_received.emit(json.loads(content))
                elif event_type == "answer_reset":
                    self.answer_reset.emit()
                elif event_type == "done" and done:
                    self.finished_ok.emit(done)
        except Exception as e:
            self.error.emit(str(e))


class ChatPanel(QWidget):
    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self.client = client
        self.conversation_id: str | None = None
        self._worker: ChatWorker | None = None
        self._assistant_buffer = ""
        self._reasoning_buffer = ""
        self._agent_steps_buffer: list[dict] = []
        self._conversation_started = False
        self._streaming = False
        self._follow_output = True
        self._scroll_guard = False
        self._stream_anchor: int | None = None
        self._stream_end: int | None = None
        self._pending_stream: tuple[str, str, list[dict], bool] | None = None
        self._stream_dirty = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("对话")
        title.setObjectName("panelTitle")
        header.addWidget(title)
        header.addStretch()

        model_label = QLabel("模型")
        model_label.setObjectName("fieldLabel")
        header.addWidget(model_label)

        self.model_combo = QComboBox()
        self.model_combo.addItems(["default", "local_ollama"])
        header.addWidget(self.model_combo)

        project_label = QLabel("项目")
        project_label.setObjectName("fieldLabel")
        header.addWidget(project_label)

        self.project_combo = QComboBox()
        self.project_combo.setMinimumWidth(140)
        header.addWidget(self.project_combo)
        layout.addLayout(header)

        self.messages = QTextEdit()
        self.messages.setObjectName("chatMessages")
        self.messages.setReadOnly(True)
        self.messages.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.messages.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.messages.installEventFilter(self)
        layout.addWidget(self.messages, stretch=1)

        scroll_bar = self.messages.verticalScrollBar()
        scroll_bar.sliderPressed.connect(self._on_user_scroll_away)
        scroll_bar.sliderReleased.connect(self._on_user_scroll_release)

        self._stream_timer = QTimer(self)
        self._stream_timer.setSingleShot(True)
        self._stream_timer.timeout.connect(self._apply_pending_stream)

        self.input_box = QTextEdit()
        self.input_box.setObjectName("chatInput")
        self.input_box.setMaximumHeight(110)
        self.input_box.setPlaceholderText("输入消息…  Ctrl + Enter 发送")
        layout.addWidget(self.input_box)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.send_btn = QPushButton("发送 →")
        self.send_btn.setObjectName("primaryButton")
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.clicked.connect(self.send_message)
        btn_row.addWidget(self.send_btn)

        self.stop_btn = QPushButton("停止")
        self.stop_btn.setObjectName("ghostButton")
        self.stop_btn.setEnabled(False)
        btn_row.addWidget(self.stop_btn)

        btn_row.addStretch()

        self.clear_btn = QPushButton("新对话")
        self.clear_btn.setObjectName("ghostButton")
        self.clear_btn.clicked.connect(self.new_conversation)
        btn_row.addWidget(self.clear_btn)
        layout.addLayout(btn_row)

        self.input_box.keyPressEvent = self._wrap_key_event(self.input_box.keyPressEvent)
        self._show_welcome()
        self._load_projects()

    def _load_projects(self) -> None:
        self.project_combo.blockSignals(True)
        self.project_combo.clear()
        self.project_combo.addItem("（无项目）", "")
        try:
            for p in self.client.get("/projects"):
                self.project_combo.addItem(p.get("name", p.get("id", "")), p.get("id", ""))
        except Exception:
            pass
        self.project_combo.blockSignals(False)

    def _current_project_id(self) -> str | None:
        value = self.project_combo.currentData()
        return value or None

    def eventFilter(self, watched, event) -> bool:
        if watched is self.messages and event.type() == QEvent.Type.Wheel:
            if event.angleDelta().y() > 0:
                self._on_user_scroll_away()
            elif event.angleDelta().y() < 0:
                self._on_user_scroll_release()
        return super().eventFilter(watched, event)

    def _is_near_bottom(self) -> bool:
        bar = self.messages.verticalScrollBar()
        return bar.maximum() - bar.value() <= SCROLL_EDGE_PX

    def _on_user_scroll_away(self) -> None:
        if self._streaming:
            self._follow_output = False

    def _on_user_scroll_release(self) -> None:
        if self._is_near_bottom():
            self._follow_output = True

    def _scroll_to_bottom(self) -> None:
        if not self._follow_output:
            return

        def scroll() -> None:
            if not self._follow_output:
                return
            self._scroll_guard = True
            try:
                bar = self.messages.verticalScrollBar()
                bar.setValue(bar.maximum())
                cursor = self.messages.textCursor()
                cursor.movePosition(QTextCursor.MoveOperation.End)
                self.messages.setTextCursor(cursor)
                self.messages.ensureCursorVisible()
            finally:
                self._scroll_guard = False

        scroll()
        QTimer.singleShot(0, scroll)

    def _document_html(self, body: str) -> str:
        return f'<body style="background:transparent; margin:0; padding:4px;">{body}</body>'

    def _show_welcome(self) -> None:
        self._conversation_started = False
        self._streaming = False
        self._stream_anchor = None
        self._stream_end = None
        welcome = (
            f'<div style="color:{TEXT_MUTED}; font-size:13px; line-height:1.6; padding:20px 0;">'
            f'<span style="color:{ACCENT}; font-size:22px;">◆</span> '
            f"LocalMind 已就绪<br>"
            f"配置模型后即可开始对话，支持深度思考模型展示推理过程。"
            f"</div>"
        )
        self.messages.setHtml(self._document_html(welcome))

    def _wrap_key_event(self, original):
        def handler(event):
            if (
                event.key() == Qt.Key.Key_Return
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier
            ):
                self.send_message()
                return
            original(event)

        return handler

    def set_context_callback(self, callback) -> None:
        self._context_callback = callback

    def _ensure_conversation_started(self) -> None:
        if self._conversation_started:
            return
        self.messages.clear()
        self._conversation_started = True

    def _insert_turn_at_end(self, block: str) -> tuple[int, int]:
        """在文档末尾插入一条独立消息块，返回 (起始位置, 结束位置)。"""
        cursor = self.messages.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if self.messages.document().toPlainText().strip():
            cursor.insertBlock()
        start = cursor.position()
        cursor.insertHtml(block)
        end = cursor.position()
        self.messages.setTextCursor(cursor)
        return start, end

    def _append_html_at_end(self, block: str) -> None:
        self._insert_turn_at_end(block)
        self._scroll_to_bottom()

    def send_message(self) -> None:
        text = self.input_box.toPlainText().strip()
        if not text or self._worker and self._worker.isRunning():
            return

        self.input_box.clear()
        self._follow_output = True
        self._ensure_conversation_started()
        self._append_html_at_end(self._format_user_block(text))

        self.send_btn.setEnabled(False)
        self._assistant_buffer = ""
        self._reasoning_buffer = ""
        self._agent_steps_buffer = []
        self._streaming = True
        self._start_assistant_stream()

        model = self.model_combo.currentText()
        self._worker = ChatWorker(
            self.client, text, self.conversation_id, model, self._current_project_id()
        )
        self._worker.chunk_received.connect(self._on_chunk)
        self._worker.reasoning_received.connect(self._on_reasoning)
        self._worker.step_received.connect(self._on_step)
        self._worker.step_delta_received.connect(self._on_step_delta)
        self._worker.answer_reset.connect(self._on_answer_reset)
        self._worker.finished_ok.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _start_assistant_stream(self) -> None:
        block = self._format_assistant_block("", "")
        self._stream_anchor, self._stream_end = self._insert_turn_at_end(block)
        self._scroll_to_bottom()

    def _on_reasoning(self, chunk: str) -> None:
        if self._agent_steps_buffer:
            return
        self._reasoning_buffer += chunk
        self._queue_stream_update(
            self._assistant_buffer, self._reasoning_buffer, self._agent_steps_buffer
        )

    def _on_step(self, step: dict) -> None:
        stype = step.get("step_type", "")
        if stype == "tool_call":
            if (
                self._agent_steps_buffer
                and self._agent_steps_buffer[-1].get("step_type") == "tool_call"
                and self._agent_steps_buffer[-1].get("tool") == step.get("tool")
            ):
                merged = dict(step)
                merged.pop("_args_text", None)
                self._agent_steps_buffer[-1] = merged
            else:
                self._agent_steps_buffer.append(step)
        else:
            self._agent_steps_buffer.append(step)
        self._queue_stream_update(
            self._assistant_buffer, self._reasoning_buffer, self._agent_steps_buffer
        )

    def _on_step_delta(self, payload: dict) -> None:
        stype = payload.get("step_type", "")
        text = payload.get("text", "")
        if stype == "reasoning" and text:
            if (
                self._agent_steps_buffer
                and self._agent_steps_buffer[-1].get("step_type") == "reasoning"
            ):
                self._agent_steps_buffer[-1]["text"] += text
            else:
                self._agent_steps_buffer.append({"step_type": "reasoning", "text": text})
        elif stype == "tool_call":
            self._agent_steps_buffer.append(
                {
                    "step_type": "tool_call",
                    "tool": payload.get("tool", "tool"),
                    "arguments": {},
                    "_args_text": "",
                }
            )
        elif stype == "tool_call_args" and text:
            for step in reversed(self._agent_steps_buffer):
                if step.get("step_type") == "tool_call" and step.get("_args_text") is not None:
                    step["_args_text"] += text
                    break
        else:
            return
        self._queue_stream_update(
            self._assistant_buffer, self._reasoning_buffer, self._agent_steps_buffer
        )

    def _on_answer_reset(self) -> None:
        self._assistant_buffer = ""
        self._queue_stream_update(
            self._assistant_buffer, self._reasoning_buffer, self._agent_steps_buffer
        )

    def _on_chunk(self, chunk: str) -> None:
        self._assistant_buffer += chunk
        self._queue_stream_update(
            self._assistant_buffer, self._reasoning_buffer, self._agent_steps_buffer
        )

    def _on_done(self, data: dict) -> None:
        self._stream_timer.stop()
        reasoning = data.get("reasoning", "")
        content = data.get("content", "")
        agent_steps = data.get("agent_steps") or []
        if agent_steps:
            self._agent_steps_buffer = agent_steps
            self._reasoning_buffer = ""
        elif reasoning:
            self._reasoning_buffer = reasoning
        if content:
            self._assistant_buffer = content
        self._replace_stream_block(
            self._assistant_buffer,
            self._reasoning_buffer,
            self._agent_steps_buffer,
        )
        self._finish_stream()
        self.conversation_id = data.get("conversation_id")
        self.send_btn.setEnabled(True)
        if hasattr(self, "_context_callback"):
            self._context_callback(data)

    def _on_error(self, msg: str) -> None:
        self._stream_timer.stop()
        self._replace_stream_block(f"[错误] {msg}", "", is_error=True)
        self._finish_stream()
        self.send_btn.setEnabled(True)

    def _finish_stream(self) -> None:
        self._streaming = False
        self._stream_anchor = None
        self._stream_end = None
        self._pending_stream = None
        self._stream_dirty = False
        self._scroll_to_bottom()

    def _queue_stream_update(
        self,
        content: str,
        reasoning: str,
        agent_steps: list[dict] | None = None,
        is_error: bool = False,
    ) -> None:
        self._pending_stream = (content, reasoning, agent_steps or [], is_error)
        if self._stream_timer.isActive():
            self._stream_dirty = True
        else:
            self._stream_timer.start(STREAM_RENDER_MS)

    def _apply_pending_stream(self) -> None:
        if self._pending_stream is None:
            return
        content, reasoning, agent_steps, is_error = self._pending_stream
        self._replace_stream_block(
            content, reasoning, agent_steps, is_error=is_error
        )
        if self._stream_dirty:
            self._stream_dirty = False
            self._stream_timer.start(STREAM_RENDER_MS)

    def _replace_stream_block(
        self,
        content: str,
        reasoning: str = "",
        agent_steps: list[dict] | None = None,
        is_error: bool = False,
    ) -> None:
        if self._stream_anchor is None or self._stream_end is None:
            return

        block = self._format_assistant_block(
            content,
            reasoning,
            agent_steps=agent_steps,
            is_error=is_error,
            streaming=self._streaming,
        )
        cursor = self.messages.textCursor()
        cursor.beginEditBlock()
        cursor.setPosition(self._stream_anchor)
        cursor.setPosition(self._stream_end, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertHtml(block)
        self._stream_end = cursor.position()
        cursor.endEditBlock()
        self._scroll_to_bottom()

    def _format_assistant_block(
        self,
        content: str,
        reasoning: str = "",
        agent_steps: list[dict] | None = None,
        is_error: bool = False,
        *,
        streaming: bool = False,
    ) -> str:
        label_color = DANGER if is_error else TEXT_MUTED
        steps = agent_steps or []
        parts = [
            '<div class="chat-turn" style="display:block; clear:both; width:100%; '
            'margin-bottom:24px; padding:4px 0;">',
            f'<div style="color:{label_color}; font-size:11px; font-weight:600; '
            f'letter-spacing:1px; margin-bottom:10px;">LocalMind</div>',
        ]

        if steps:
            steps_html = render_agent_steps_html(
                steps,
                streaming=streaming and not content.strip(),
            )
            if steps_html:
                parts.append(steps_html)
        elif reasoning.strip():
            reasoning_html = render_message_body(
                reasoning, role="reasoning", streaming=streaming and not content.strip()
            )
            parts.append(
                f'<div style="margin-bottom:12px; background:#0c0c14; border-radius:12px; '
                f'padding:12px 16px; border:1px solid #3d3560;">'
                f'<div style="color:{REASONING_COLOR}; font-size:11px; font-weight:700; '
                f'letter-spacing:1px; margin-bottom:8px;">💭 思考过程</div>'
                f"{reasoning_html}</div>"
            )

        if content.strip():
            body = render_message_body(
                content,
                role="assistant",
                is_error=is_error,
                streaming=streaming,
            )
            border_color = DANGER if is_error else "#1e1e2a"
            parts.append(
                f'<div style="background:{BG_CARD}; border-radius:12px; padding:14px 18px; '
                f'border:1px solid {border_color};">{body}</div>'
            )
        elif steps and streaming:
            parts.append(
                f'<div style="color:{TEXT_MUTED}; font-size:13px; padding:8px 0;">'
                f"...</div>"
            )
        elif not reasoning.strip() and not steps:
            parts.append(
                f'<div style="color:{TEXT_MUTED}; font-size:13px; padding:8px 0;">...</div>'
            )

        parts.append("</div>")
        return "".join(parts)

    def _format_user_block(self, content: str) -> str:
        body = render_message_body(content, role="user")
        return (
            f'<div class="chat-turn" style="display:block; clear:both; width:100%; '
            f'margin-bottom:24px; padding:4px 0;">'
            f'<div style="color:{TEXT_MUTED}; font-size:11px; font-weight:600; '
            f'letter-spacing:1px; margin-bottom:10px; text-align:right;">你</div>'
            f'<div style="background:#141a28; border-radius:12px; padding:14px 18px; '
            f'border:1px solid #1e2a3a; margin-left:24px;">{body}</div>'
            f"</div>"
        )

    def new_conversation(self) -> None:
        self.conversation_id = None
        self._show_welcome()
        if hasattr(self, "_context_callback") and callable(self._context_callback):
            self._context_callback({})

    def load_conversation(self, conv_id: str) -> None:
        self.conversation_id = conv_id
        self._conversation_started = True
        self._streaming = False
        self._stream_anchor = None
        self._stream_end = None
        self._follow_output = True
        try:
            msgs = self.client.get(f"/conversations/{conv_id}/messages")
            blocks: list[str] = []
            for m in msgs:
                if m["role"] == "user":
                    blocks.append(self._format_user_block(m["content"]))
                else:
                    reasoning, answer, agent_steps = parse_assistant_message(m["content"])
                    blocks.append(
                        self._format_assistant_block(
                            answer, reasoning, agent_steps=agent_steps
                        )
                    )
            self.messages.setHtml(self._document_html("".join(blocks)))
            self._scroll_to_bottom()
        except Exception as e:
            self.messages.setHtml(
                self._document_html(self._format_assistant_block(f"加载失败: {e}", "", is_error=True))
            )
            self._scroll_to_bottom()
