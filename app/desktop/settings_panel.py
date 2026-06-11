"""设置面板."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.desktop.api_client import ApiClient


class SettingsPanel(QWidget):
    _LABEL_WIDTH = 120
    _FIELD_HEIGHT = 42
    _ROW_HEIGHT = 50
    _ROW_GAP = 6

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self.client = client

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        title = QLabel("设置")
        title.setObjectName("panelTitle")
        root.addWidget(title)

        scroll = QScrollArea()
        scroll.setObjectName("settingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 8, 0)
        body_layout.setSpacing(14)

        # ── 模型配置 ──
        model_group, model_layout = self._section("模型配置")
        self.provider_combo = self._combo(editable=False)
        self.provider_type = self._combo(
            ["openai_compatible", "ollama"], editable=False
        )
        self.base_url = self._line_edit()
        self.api_key = self._line_edit(password=True, placeholder="留空则保持原 Key")
        self.chat_model = self._line_edit()
        self.embedding_model = self._line_edit()
        self.temperature_combo = self._combo(
            ["0.0", "0.3", "0.5", "0.7", "1.0", "1.2", "1.5", "2.0"], editable=True
        )
        self.max_tokens_combo = self._combo(
            ["4096", "8192", "16384", "32768"], editable=True
        )

        for label, widget in (
            ("Provider", self.provider_combo),
            ("类型", self.provider_type),
            ("Base URL", self.base_url),
            ("API Key", self.api_key),
            ("对话模型", self.chat_model),
            ("向量模型", self.embedding_model),
            ("Temperature", self.temperature_combo),
            ("Max Tokens", self.max_tokens_combo),
        ):
            model_layout.addWidget(self._field_row(label, widget))
        body_layout.addWidget(model_group)

        # ── 隐私配置 ──
        privacy_group, privacy_layout = self._section("隐私配置")
        self.local_only = self._checkbox("本地优先模式")
        self.send_path = self._checkbox("向模型发送文件路径")
        self.send_memory = self._checkbox("向模型发送记忆片段")
        self._checkbox_list(
            privacy_layout,
            [self.local_only, self.send_path, self.send_memory],
        )
        body_layout.addWidget(privacy_group)

        # ── 记忆配置 ──
        memory_group, memory_layout = self._section("记忆配置")
        self.auto_memory = self._checkbox("对话后自动抽取并保存记忆")
        self.auto_memory.setToolTip(
            "对话结束后在后台分析并写入长期记忆，可在「记忆」页查看"
        )
        self._checkbox_list(memory_layout, [self.auto_memory])
        body_layout.addWidget(memory_group)

        # ── Agent / 工具 ──
        agent_group, agent_layout = self._section("Agent / 工具 (v0.3)")
        self.tools_enabled = self._checkbox("启用本地工具调用")
        self.auto_confirm_write = self._checkbox("自动确认文件覆盖")
        self.skill_network = self._checkbox("允许 Skill 使用网络")
        self.shell_tool = self._checkbox("允许 Shell 工具")
        self._checkbox_list(
            agent_layout,
            [
                self.tools_enabled,
                self.auto_confirm_write,
                self.skill_network,
                self.shell_tool,
            ],
        )
        self.agent_max_steps_combo = self._combo(
            ["4", "6", "8", "10", "12", "16", "20"], editable=False
        )
        agent_layout.addWidget(self._field_row("最大执行步骤", self.agent_max_steps_combo))
        body_layout.addWidget(agent_group)

        # ── 路径配置 ──
        path_group, path_layout = self._section("路径配置")
        self.workspace_dir = self._line_edit()
        self.knowledge_dir = self._line_edit()
        path_layout.addWidget(self._field_row("工作区", self.workspace_dir))
        path_layout.addWidget(self._field_row("知识库", self.knowledge_dir))
        body_layout.addWidget(path_group)

        body_layout.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, stretch=1)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("保存设置")
        save_btn.setObjectName("primaryButton")
        save_btn.setMinimumHeight(40)
        save_btn.clicked.connect(self.save)
        reload_btn = QPushButton("重新加载")
        reload_btn.setObjectName("ghostButton")
        reload_btn.setMinimumHeight(40)
        reload_btn.clicked.connect(self.reload)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(reload_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        self.load()

    @classmethod
    def _section(cls, title: str) -> tuple[QGroupBox, QVBoxLayout]:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(18, 26, 18, 16)
        layout.setSpacing(cls._ROW_GAP)
        return group, layout

    @classmethod
    def _style_field(cls, widget: QWidget) -> None:
        widget.setObjectName("settingsField")
        widget.setFixedHeight(cls._FIELD_HEIGHT)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    @classmethod
    def _line_edit(
        cls, *, password: bool = False, placeholder: str = ""
    ) -> QLineEdit:
        edit = QLineEdit()
        if password:
            edit.setEchoMode(QLineEdit.EchoMode.Password)
        if placeholder:
            edit.setPlaceholderText(placeholder)
        cls._style_field(edit)
        return edit

    @classmethod
    def _combo(
        cls, items: list[str] | None = None, *, editable: bool = False
    ) -> QComboBox:
        combo = QComboBox()
        if items:
            combo.addItems(items)
        combo.setEditable(editable)
        if editable:
            combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        cls._style_field(combo)
        return combo

    @classmethod
    def _checkbox(cls, text: str) -> QCheckBox:
        cb = QCheckBox(text)
        cb.setObjectName("settingsCheckBox")
        cb.setMinimumHeight(36)
        return cb

    @classmethod
    def _field_row(cls, label: str, field: QWidget) -> QWidget:
        row = QWidget()
        row.setFixedHeight(cls._ROW_HEIGHT)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        lbl = QLabel(label)
        lbl.setObjectName("settingsFormLabel")
        lbl.setFixedWidth(cls._LABEL_WIDTH)
        lbl.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        layout.addWidget(lbl)
        layout.addWidget(field, 1)
        return row

    @classmethod
    def _checkbox_list(cls, parent: QVBoxLayout, boxes: list[QCheckBox]) -> None:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(cls._LABEL_WIDTH + 14, 0, 0, 0)
        layout.setSpacing(4)
        for box in boxes:
            layout.addWidget(box)
        parent.addWidget(wrap)

    def load(self) -> None:
        try:
            data = self.client.get("/settings")
            settings = data["settings"]
            providers = data["providers"]

            self.provider_combo.blockSignals(True)
            self.provider_combo.clear()
            self.provider_combo.addItems(list(providers.keys()))
            self.provider_combo.setCurrentText(data.get("active_provider", "default"))
            self.provider_combo.blockSignals(False)

            self._fill_provider(providers.get(self.provider_combo.currentText(), {}))

            self.local_only.setChecked(settings.get("local_only_mode", True))
            self.send_path.setChecked(settings.get("send_file_path_to_model", False))
            self.send_memory.setChecked(settings.get("send_memory_to_model", True))
            self.auto_memory.setChecked(settings.get("auto_memory_enabled", True))
            self.tools_enabled.setChecked(settings.get("tools_enabled", True))
            self.auto_confirm_write.setChecked(
                settings.get("auto_confirm_file_write", False)
            )
            self.skill_network.setChecked(settings.get("skill_network_enabled", False))
            self.shell_tool.setChecked(settings.get("shell_tool_enabled", False))
            self._set_combo_text(
                self.agent_max_steps_combo, str(settings.get("agent_max_steps", 8))
            )
            self.workspace_dir.setText(settings.get("workspace_dir", ""))
            self.knowledge_dir.setText(settings.get("knowledge_dir", ""))
        except Exception as e:
            QMessageBox.warning(self, "加载失败", str(e))

    def reload(self) -> None:
        self.load()

    def _on_provider_changed(self, name: str) -> None:
        try:
            data = self.client.get("/settings")
            self._fill_provider(data["providers"].get(name, {}))
        except Exception:
            pass

    @staticmethod
    def _set_combo_text(combo: QComboBox, value: str) -> None:
        idx = combo.findText(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)
        elif combo.isEditable():
            combo.setEditText(value)
        elif combo.count():
            combo.setCurrentIndex(0)

    def _fill_provider(self, p: dict) -> None:
        idx = self.provider_type.findText(p.get("type", "openai_compatible"))
        self.provider_type.setCurrentIndex(max(0, idx))
        self.base_url.setText(p.get("base_url", ""))
        masked = p.get("api_key_masked", "")
        self.api_key.setPlaceholderText(f"已保存: {masked}" if masked else "输入 API Key")
        self.api_key.clear()
        self.chat_model.setText(p.get("chat_model", ""))
        self.embedding_model.setText(p.get("embedding_model", ""))
        self._set_combo_text(self.temperature_combo, str(p.get("temperature", 0.7)))
        self._set_combo_text(self.max_tokens_combo, str(p.get("max_tokens", 4096)))

    def save(self) -> None:
        try:
            provider_name = self.provider_combo.currentText()
            temperature = float(self.temperature_combo.currentText().strip() or "0.7")
            max_tokens = int(self.max_tokens_combo.currentText().strip() or "4096")
            agent_steps = int(self.agent_max_steps_combo.currentText().strip() or "8")

            self.client.put(
                "/settings/providers",
                {
                    "active_provider": provider_name,
                    "providers": {
                        provider_name: {
                            "type": self.provider_type.currentText(),
                            "base_url": self.base_url.text(),
                            "api_key": self.api_key.text(),
                            "chat_model": self.chat_model.text(),
                            "embedding_model": self.embedding_model.text(),
                            "temperature": temperature,
                            "max_tokens": max_tokens,
                        }
                    },
                },
            )
            self.client.put(
                "/settings",
                {
                    "local_only_mode": self.local_only.isChecked(),
                    "send_file_path_to_model": self.send_path.isChecked(),
                    "send_memory_to_model": self.send_memory.isChecked(),
                    "auto_memory_enabled": self.auto_memory.isChecked(),
                    "tools_enabled": self.tools_enabled.isChecked(),
                    "auto_confirm_file_write": self.auto_confirm_write.isChecked(),
                    "skill_network_enabled": self.skill_network.isChecked(),
                    "shell_tool_enabled": self.shell_tool.isChecked(),
                    "agent_max_steps": agent_steps,
                    "workspace_dir": self.workspace_dir.text(),
                    "knowledge_dir": self.knowledge_dir.text(),
                    "active_provider": provider_name,
                },
            )
            QMessageBox.information(self, "成功", "设置已保存")
            self.load()
        except Exception as e:
            QMessageBox.warning(self, "保存失败", str(e))
