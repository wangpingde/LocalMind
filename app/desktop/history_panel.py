"""历史对话浏览面板."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.desktop.api_client import ApiClient

_SCOPE_OPTIONS = [
    ("今天", "today"),
    ("近 7 天", "week"),
    ("近 30 天", "month"),
    ("全部", "all"),
]


def _format_time(iso_ts: str | None) -> str:
    if not iso_ts:
        return "-"
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            from datetime import timezone

            dt = dt.replace(tzinfo=timezone.utc)
        local = dt.astimezone()
        today = datetime.now().astimezone().date()
        if local.date() == today:
            return local.strftime("%H:%M")
        if local.year == today.year:
            return local.strftime("%m-%d %H:%M")
        return local.strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso_ts[:16] if iso_ts else "-"


class HistoryPanel(QWidget):
    conversation_open_requested = Signal(str)

    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self.client = client
        self._conversations: list[dict] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        title = QLabel("历史对话")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        hint = QLabel("浏览并打开过往会话；侧栏「历史」默认仅显示今天的快捷入口。")
        hint.setObjectName("panelSubtitle")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)

        self.scope_combo = QComboBox()
        for label, value in _SCOPE_OPTIONS:
            self.scope_combo.addItem(label, value)
        self.scope_combo.currentIndexChanged.connect(self.refresh)

        self.keyword_input = QLineEdit()
        self.keyword_input.setPlaceholderText("按标题搜索...")
        self.keyword_input.returnPressed.connect(self.refresh)

        search_btn = QPushButton("搜索")
        search_btn.setObjectName("ghostButton")
        search_btn.clicked.connect(self.refresh)

        filter_row.addWidget(QLabel("范围:"))
        filter_row.addWidget(self.scope_combo)
        filter_row.addWidget(self.keyword_input, stretch=1)
        filter_row.addWidget(search_btn)
        layout.addLayout(filter_row)

        self.stats_label = QLabel("")
        self.stats_label.setObjectName("panelSubtitle")
        layout.addWidget(self.stats_label)

        self.table = QTableWidget(0, 3)
        self.table.setObjectName("dataTable")
        self.table.setHorizontalHeaderLabels(["标题", "最近更新", "创建时间"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.doubleClicked.connect(self._open_selected)
        layout.addWidget(self.table, stretch=1)

        btn_row = QHBoxLayout()
        open_btn = QPushButton("打开会话")
        open_btn.setObjectName("primaryButton")
        open_btn.clicked.connect(self._open_selected)
        delete_btn = QPushButton("删除")
        delete_btn.setObjectName("ghostButton")
        delete_btn.clicked.connect(self._delete_selected)
        refresh_btn = QPushButton("刷新")
        refresh_btn.setObjectName("ghostButton")
        refresh_btn.clicked.connect(self.refresh)
        btn_row.addWidget(open_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.refresh()

    def _query_params(self) -> str:
        scope = self.scope_combo.currentData() or "today"
        params = f"scope={scope}"
        keyword = self.keyword_input.text().strip()
        if keyword:
            from urllib.parse import quote

            params += f"&keyword={quote(keyword)}"
        return params

    def refresh(self) -> None:
        try:
            self._conversations = self.client.get(f"/conversations?{self._query_params()}")
            self._fill_table()
            scope_label = self.scope_combo.currentText()
            kw = self.keyword_input.text().strip()
            extra = f" · 关键词「{kw}」" if kw else ""
            self.stats_label.setText(
                f"共 {len(self._conversations)} 条 · 范围: {scope_label}{extra}"
            )
        except Exception as e:
            self.stats_label.setText(f"加载失败: {e}")
            self.table.setRowCount(0)

    def _fill_table(self) -> None:
        self.table.setRowCount(len(self._conversations))
        for i, conv in enumerate(self._conversations):
            title = (conv.get("title") or "对话").strip() or "对话"
            title_item = QTableWidgetItem(title)
            title_item.setData(Qt.ItemDataRole.UserRole, conv.get("id"))
            title_item.setToolTip(title)
            self.table.setItem(i, 0, title_item)
            self.table.setItem(i, 1, QTableWidgetItem(_format_time(conv.get("updated_at"))))
            self.table.setItem(i, 2, QTableWidgetItem(_format_time(conv.get("created_at"))))

    def _selected_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _open_selected(self) -> None:
        conv_id = self._selected_id()
        if not conv_id:
            QMessageBox.information(self, "提示", "请先选择一条会话")
            return
        self.conversation_open_requested.emit(conv_id)

    def _delete_selected(self) -> None:
        conv_id = self._selected_id()
        if not conv_id:
            QMessageBox.information(self, "提示", "请先选择一条会话")
            return
        if (
            QMessageBox.question(
                self,
                "确认",
                "确定永久删除该会话？\n将删除所有消息与 Agent 记录，不可恢复。",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            self.client.delete(f"/conversations/{conv_id}")
            self.refresh()
        except Exception as e:
            QMessageBox.warning(self, "删除失败", str(e))
