"""记忆面板."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QInputDialog,
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

MEMORY_TYPES = ["profile", "preference", "project", "skill", "episodic", "semantic"]


class MemoryPanel(QWidget):
    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self.client = client
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        title = QLabel("长期记忆")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        filter_row = QHBoxLayout()
        self.type_filter = QComboBox()
        self.type_filter.addItem("全部类型", "")
        for t in MEMORY_TYPES:
            self.type_filter.addItem(t, t)
        self.keyword = QLineEdit()
        self.keyword.setPlaceholderText("搜索关键词...")
        search_btn = QPushButton("搜索")
        search_btn.clicked.connect(self.refresh)
        filter_row.addWidget(QLabel("类型:"))
        filter_row.addWidget(self.type_filter)
        filter_row.addWidget(self.keyword)
        filter_row.addWidget(search_btn)
        layout.addLayout(filter_row)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["类型", "内容", "状态", "标签", "更新时间"])
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("新增")
        add_btn.setObjectName("primaryButton")
        add_btn.clicked.connect(self.add_memory)
        edit_btn = QPushButton("编辑")
        edit_btn.setObjectName("ghostButton")
        edit_btn.clicked.connect(self.edit_memory)
        del_btn = QPushButton("删除")
        del_btn.setObjectName("ghostButton")
        del_btn.clicked.connect(self.delete_memory)
        disable_btn = QPushButton("禁用")
        disable_btn.setObjectName("ghostButton")
        disable_btn.clicked.connect(self.disable_memory)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(del_btn)
        btn_row.addWidget(disable_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.refresh()

    def refresh(self) -> None:
        try:
            type_val = self.type_filter.currentData()
            keyword = self.keyword.text().strip() or None
            path = "/memories"
            params = []
            if type_val:
                params.append(f"type={type_val}")
            if keyword:
                params.append(f"keyword={keyword}")
            if params:
                path += "?" + "&".join(params)
            memories = self.client.get(path)
            self.table.setRowCount(len(memories))
            for i, m in enumerate(memories):
                self.table.setItem(i, 0, QTableWidgetItem(m.get("type", "")))
                item = QTableWidgetItem(m.get("content", "")[:100])
                item.setData(256, m.get("id"))
                self.table.setItem(i, 1, item)
                self.table.setItem(i, 2, QTableWidgetItem(m.get("status", "")))
                tags = ", ".join(m.get("tags", []))
                self.table.setItem(i, 3, QTableWidgetItem(tags))
                self.table.setItem(i, 4, QTableWidgetItem(m.get("updated_at", "")))
        except Exception as e:
            QMessageBox.warning(self, "加载失败", str(e))

    def _selected_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 1)
        return item.data(256) if item else None

    def add_memory(self) -> None:
        content, ok = QInputDialog.getMultiLineText(self, "新增记忆", "记忆内容:")
        if not ok or not content.strip():
            return
        mtype, ok2 = QInputDialog.getItem(self, "记忆类型", "选择类型:", MEMORY_TYPES, 0, False)
        if not ok2:
            return
        try:
            self.client.post("/memories", {"type": mtype, "content": content.strip(), "tags": []})
            self.refresh()
        except Exception as e:
            QMessageBox.warning(self, "失败", str(e))

    def edit_memory(self) -> None:
        mid = self._selected_id()
        if not mid:
            QMessageBox.information(self, "提示", "请先选择一条记忆")
            return
        row = self.table.currentRow()
        old = self.table.item(row, 1).text()
        content, ok = QInputDialog.getMultiLineText(self, "编辑记忆", "记忆内容:", old)
        if not ok:
            return
        try:
            self.client.put(f"/memories/{mid}", {"content": content})
            self.refresh()
        except Exception as e:
            QMessageBox.warning(self, "失败", str(e))

    def delete_memory(self) -> None:
        mid = self._selected_id()
        if not mid:
            return
        if (
            QMessageBox.question(self, "确认", "确定永久删除该记忆？此操作不可恢复。")
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            self.client.delete(f"/memories/{mid}")
            self.refresh()
        except Exception as e:
            QMessageBox.warning(self, "失败", str(e))

    def disable_memory(self) -> None:
        mid = self._selected_id()
        if not mid:
            return
        try:
            self.client.put(f"/memories/{mid}", {"status": "disabled"})
            self.refresh()
        except Exception as e:
            QMessageBox.warning(self, "失败", str(e))
