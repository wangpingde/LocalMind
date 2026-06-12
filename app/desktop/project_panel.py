"""项目空间面板."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.desktop.api_client import ApiClient


class ProjectPanel(QWidget):
    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self.client = client
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        title = QLabel("项目空间")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        hint = QLabel("每个项目拥有独立知识库目录 knowledge/projects/<slug>/")
        hint.setObjectName("panelSubtitle")
        layout.addWidget(hint)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["名称", "标识", "知识库路径", "说明"])
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        form_row = QHBoxLayout()
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("项目名称")
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("项目说明（可选）")
        self.desc_input.setMaximumHeight(60)
        form_row.addWidget(self.name_input, stretch=2)
        form_row.addWidget(self.desc_input, stretch=3)
        layout.addLayout(form_row)

        btn_row = QHBoxLayout()
        create_btn = QPushButton("创建项目")
        create_btn.setObjectName("primaryButton")
        create_btn.clicked.connect(self.create_project)
        refresh_btn = QPushButton("刷新")
        refresh_btn.setObjectName("ghostButton")
        refresh_btn.clicked.connect(self.refresh)
        delete_btn = QPushButton("删除")
        delete_btn.setObjectName("ghostButton")
        delete_btn.clicked.connect(self.delete_project)
        open_btn = QPushButton("打开目录")
        open_btn.setObjectName("ghostButton")
        open_btn.clicked.connect(self.open_folder)
        btn_row.addWidget(create_btn)
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addWidget(open_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.refresh()

    def refresh(self) -> None:
        try:
            projects = self.client.get("/projects")
            self.table.setRowCount(len(projects))
            for i, p in enumerate(projects):
                item = QTableWidgetItem(p.get("name", ""))
                item.setData(256, p.get("id"))
                self.table.setItem(i, 0, item)
                self.table.setItem(i, 1, QTableWidgetItem(p.get("slug", "")))
                self.table.setItem(i, 2, QTableWidgetItem(p.get("knowledge_path", "")))
                self.table.setItem(i, 3, QTableWidgetItem(p.get("description", "")))
        except Exception as e:
            QMessageBox.warning(self, "加载失败", str(e))

    def _selected_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(256) if item else None

    def create_project(self) -> None:
        name = self.name_input.text().strip()
        if not name:
            QMessageBox.information(self, "提示", "请输入项目名称")
            return
        try:
            self.client.post(
                "/projects",
                {"name": name, "description": self.desc_input.toPlainText().strip()},
            )
            self.name_input.clear()
            self.desc_input.clear()
            self.refresh()
        except Exception as e:
            QMessageBox.warning(self, "创建失败", str(e))

    def delete_project(self) -> None:
        pid = self._selected_id()
        if not pid:
            QMessageBox.information(self, "提示", "请先选择项目")
            return
        if (
            QMessageBox.question(
                self,
                "确认",
                "确定永久删除该项目？\n将删除项目目录及其中所有文件，并清理相关索引，不可恢复。",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            self.client.delete(f"/projects/{pid}")
            self.refresh()
        except Exception as e:
            QMessageBox.warning(self, "删除失败", str(e))

    def open_folder(self) -> None:
        pid = self._selected_id()
        if not pid:
            QMessageBox.information(self, "提示", "请先选择项目")
            return
        row = self.table.currentRow()
        path_item = self.table.item(row, 2)
        if not path_item:
            return
        import subprocess
        import sys

        path = path_item.text()
        if not path:
            return
        if sys.platform == "win32":
            subprocess.Popen(["explorer", path])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
