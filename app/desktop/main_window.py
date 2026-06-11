"""主窗口."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

_HISTORY_TITLE_ROLE = Qt.ItemDataRole.UserRole + 1

from app.desktop.api_client import ApiClient
from app.desktop.chat_panel import ChatPanel
from app.desktop.context_panel import ContextPanel
from app.desktop.knowledge_panel import KnowledgePanel
from app.desktop.memory_panel import MemoryPanel
from app.desktop.project_panel import ProjectPanel
from app.desktop.settings_panel import SettingsPanel
from app.desktop.skill_panel import SkillPanel


class MainWindow(QMainWindow):
    def __init__(self, api_port: int = 17777) -> None:
        super().__init__()
        self.setWindowTitle("LocalMind")
        self.resize(1360, 860)
        self.setMinimumSize(960, 600)

        self.client = ApiClient(f"http://127.0.0.1:{api_port}")

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(6)
        self.splitter.setChildrenCollapsible(False)

        # ── 左侧导航（可拖拽加宽）──
        self.nav_widget = QWidget()
        self.nav_widget.setObjectName("sidebar")
        self.nav_widget.setMinimumWidth(200)
        self.nav_widget.setMaximumWidth(480)
        nav_layout = QVBoxLayout(self.nav_widget)
        nav_layout.setContentsMargins(12, 20, 12, 16)
        nav_layout.setSpacing(6)

        brand = QLabel("◆ LocalMind")
        brand.setObjectName("brandTitle")
        brand.setWordWrap(True)
        nav_layout.addWidget(brand)

        subtitle = QLabel("LOCAL AGENT")
        subtitle.setObjectName("brandSubtitle")
        nav_layout.addWidget(subtitle)

        nav_layout.addSpacing(16)

        nav_label = QLabel("导航")
        nav_label.setObjectName("sectionLabel")
        nav_layout.addWidget(nav_label)

        self.nav_list = QListWidget()
        self.nav_list.setObjectName("navList")
        self.nav_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.nav_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        nav_items = ["聊天", "历史对话", "知识库", "项目", "记忆", "Skills", "设置"]
        for label in nav_items:
            item = QListWidgetItem(label)
            item.setToolTip(label)
            self.nav_list.addItem(item)
        self.nav_list.setMinimumHeight(len(nav_items) * 40 + 8)
        self.nav_list.setCurrentRow(0)
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)
        nav_layout.addWidget(self.nav_list, stretch=0)

        nav_layout.addSpacing(8)

        history_label = QLabel("历史")
        history_label.setObjectName("sectionLabel")
        nav_layout.addWidget(history_label)

        self.history_list = QListWidget()
        self.history_list.setObjectName("historyList")
        self.history_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.history_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.history_list.setWordWrap(False)
        self.history_list.itemClicked.connect(self._on_history_clicked)
        self.history_list.viewport().installEventFilter(self)
        nav_layout.addWidget(self.history_list, stretch=1)

        self._load_history()
        self.splitter.addWidget(self.nav_widget)

        # ── 中间内容区 ──
        self.stack = QStackedWidget()
        self.chat_panel = ChatPanel(self.client)
        self.knowledge_panel = KnowledgePanel(self.client)
        self.project_panel = ProjectPanel(self.client)
        self.memory_panel = MemoryPanel(self.client)
        self.skill_panel = SkillPanel(self.client)
        self.settings_panel = SettingsPanel(self.client)

        placeholder = QWidget()
        self.stack.addWidget(self.chat_panel)
        self.stack.addWidget(placeholder)
        self.stack.addWidget(self.knowledge_panel)
        self.stack.addWidget(self.project_panel)
        self.stack.addWidget(self.memory_panel)
        self.stack.addWidget(self.skill_panel)
        self.stack.addWidget(self.settings_panel)
        self.splitter.addWidget(self.stack)

        # ── 右侧上下文 ──
        self.context_panel = ContextPanel(self.client)
        self.context_panel.setMinimumWidth(280)
        self.context_panel.setMaximumWidth(420)
        self.splitter.addWidget(self.context_panel)

        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([280, 720, 340])
        self.splitter.splitterMoved.connect(self._on_sidebar_resized)

        main_layout.addWidget(self.splitter)

        self.chat_panel.set_context_callback(self.context_panel.update_context)

    def _on_nav_changed(self, index: int) -> None:
        if index == 1:
            self._load_history()
            self.stack.setCurrentIndex(0)
            return
        mapping = {0: 0, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6}
        self.stack.setCurrentIndex(mapping.get(index, 0))
        if index == 0:
            self.chat_panel._load_projects()

    def eventFilter(self, watched, event) -> bool:
        if watched is self.history_list.viewport() and event.type() == QEvent.Type.Resize:
            self._refresh_history_labels()
        return super().eventFilter(watched, event)

    def _on_sidebar_resized(self, _pos: int, _index: int) -> None:
        self._refresh_history_labels()
        self._refresh_nav_labels()

    def _elide_text(self, text: str, widget: QListWidget, padding: int = 20) -> str:
        width = max(80, widget.viewport().width() - padding)
        return QFontMetrics(widget.font()).elidedText(
            text, Qt.TextElideMode.ElideRight, width
        )

    def _refresh_nav_labels(self) -> None:
        for i in range(self.nav_list.count()):
            item = self.nav_list.item(i)
            if not item:
                continue
            full = item.toolTip() or item.text()
            item.setText(self._elide_text(full, self.nav_list))

    def _refresh_history_labels(self) -> None:
        for i in range(self.history_list.count()):
            item = self.history_list.item(i)
            if not item:
                continue
            full = item.data(_HISTORY_TITLE_ROLE) or item.toolTip() or item.text()
            item.setText(self._elide_text(full, self.history_list))

    def _load_history(self) -> None:
        self.history_list.clear()
        try:
            convs = self.client.get("/conversations")
            for c in convs:
                title = (c.get("title") or "对话").strip() or "对话"
                conv_id = c["id"]
                item = QListWidgetItem()
                item.setData(Qt.ItemDataRole.UserRole, conv_id)
                item.setData(_HISTORY_TITLE_ROLE, title)
                item.setToolTip(title)
                item.setText(self._elide_text(title, self.history_list))
                self.history_list.addItem(item)
        except Exception:
            pass

    def _on_history_clicked(self, item) -> None:
        conv_id = item.data(Qt.ItemDataRole.UserRole)
        if conv_id:
            self.nav_list.setCurrentRow(0)
            self.stack.setCurrentIndex(0)
            self.chat_panel.load_conversation(conv_id)
            self.context_panel.clear()

    def check_server(self) -> bool:
        try:
            self.client.get("/health")
            return True
        except Exception as e:
            QMessageBox.critical(
                self,
                "服务未就绪",
                f"本地 API 服务未启动或无法连接:\n{e}\n\n请重启应用。",
            )
            return False
