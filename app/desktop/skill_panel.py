"""Skill 面板."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.core.skills.skill_presenter import format_package_badge
from app.desktop.api_client import ApiClient


def _format_skill_detail(data: dict) -> str:
    lines = [
        f"# {data.get('name', '')} (`{data.get('id', '')}`)",
        f"版本: {data.get('version', '')}",
        f"描述: {data.get('description', '')}",
        "",
        "## 权限",
    ]
    for line in data.get("permission_summary") or []:
        lines.append(f"- {line}")
    allowed = data.get("allowed", True)
    lines.append(f"- 全局允许: {'是' if allowed else '否（部分能力受限）'}")

    pkg_info = data.get("package") or {}
    lines.extend(
        [
            "",
            "## 标准目录",
            f"- agents: {pkg_info.get('agents_count', 0)}",
            f"- scripts: {pkg_info.get('scripts_count', 0)}",
            f"- assets: {pkg_info.get('assets_count', 0)}",
            f"- references: {'有' if pkg_info.get('has_references') else '无'}",
        ]
    )

    for section, key, label in (
        ("agents", "agents", "子 Agent"),
        ("scripts", "scripts", "脚本"),
        ("assets", "assets", "资产"),
    ):
        items = data.get(key) or []
        if items:
            lines.append(f"\n## {label}")
            for item in items:
                if section == "agents":
                    tools = ", ".join(item.get("tools") or [])
                    extra = f" · 工具: {tools}" if tools else ""
                    lines.append(f"- **{item.get('name')}**: {item.get('description', '')}{extra}")
                elif section == "scripts":
                    desc = item.get("description") or ""
                    suffix = f" — {desc}" if desc else ""
                    lines.append(f"- `{item.get('filename')}`{suffix}")
                else:
                    size_kb = (item.get("size") or 0) / 1024
                    lines.append(f"- `{item.get('path')}` ({size_kb:.1f} KB)")

    kws = data.get("triggers_keywords") or []
    if kws:
        lines.extend(["", "## 触发关键词", ", ".join(kws)])
    return "\n".join(lines)


class SkillDetailDialog(QDialog):
    def __init__(self, client: ApiClient, skill_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Skill 详情")
        self.resize(520, 480)
        layout = QVBoxLayout(self)
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.text)
        close_btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_btn.rejected.connect(self.reject)
        layout.addWidget(close_btn)
        try:
            data = client.get(f"/skills/{skill_id}")
            self.setWindowTitle(f"Skill 详情 — {data.get('name', skill_id)}")
            self.text.setMarkdown(_format_skill_detail(data))
        except Exception as e:
            self.text.setPlainText(f"加载失败: {e}")


class SkillMarketDialog(QDialog):
    def __init__(self, client: ApiClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.client = client
        self.setWindowTitle("Skill 市场")
        self.resize(560, 360)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("浏览并安装官方 Skill 包（本地市场雏形）"))

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["名称", "版本", "描述", "资源", "状态"])
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        buttons = QDialogButtonBox()
        install_btn = buttons.addButton("安装选中", QDialogButtonBox.ButtonRole.AcceptRole)
        close_btn = buttons.addButton("关闭", QDialogButtonBox.ButtonRole.RejectRole)
        install_btn.clicked.connect(self._install_selected)
        close_btn.clicked.connect(self.reject)
        layout.addWidget(buttons)
        self._load()

    def _load(self) -> None:
        try:
            data = self.client.get("/skills/market")
            skills = data.get("skills", [])
            self.table.setRowCount(len(skills))
            for i, s in enumerate(skills):
                item = QTableWidgetItem(s.get("name", ""))
                item.setData(256, s.get("id"))
                self.table.setItem(i, 0, item)
                self.table.setItem(i, 1, QTableWidgetItem(s.get("version", "")))
                self.table.setItem(i, 2, QTableWidgetItem(s.get("description", "")))
                self.table.setItem(i, 3, QTableWidgetItem(format_package_badge(s.get("package"))))
                status = "已安装" if s.get("installed") else "可安装"
                self.table.setItem(i, 4, QTableWidgetItem(status))
        except Exception as e:
            QMessageBox.warning(self, "加载失败", str(e))

    def _install_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "提示", "请选择一个 Skill")
            return
        item = self.table.item(row, 0)
        skill_id = item.data(256) if item else None
        if not skill_id:
            return
        try:
            self.client.post(f"/skills/market/{skill_id}/install?replace=false")
            QMessageBox.information(self, "成功", f"已安装 {item.text()}")
            self._load()
        except Exception as e:
            QMessageBox.warning(self, "安装失败", str(e))


class SkillPanel(QWidget):
    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self.client = client
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        title = QLabel("Skills")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["名称", "描述", "资源", "状态", "权限", "关键词"])
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("刷新")
        refresh_btn.setObjectName("ghostButton")
        refresh_btn.clicked.connect(self.refresh)
        reload_btn = QPushButton("重新加载")
        reload_btn.setObjectName("ghostButton")
        reload_btn.clicked.connect(self.reload)
        market_btn = QPushButton("市场")
        market_btn.setObjectName("primaryButton")
        market_btn.clicked.connect(self.open_market)
        install_btn = QPushButton("安装 ZIP")
        install_btn.setObjectName("ghostButton")
        install_btn.clicked.connect(self.install_zip)
        enable_btn = QPushButton("启用")
        enable_btn.setObjectName("primaryButton")
        enable_btn.clicked.connect(lambda: self._toggle(True))
        disable_btn = QPushButton("禁用")
        disable_btn.setObjectName("ghostButton")
        disable_btn.clicked.connect(lambda: self._toggle(False))
        uninstall_btn = QPushButton("卸载")
        uninstall_btn.setObjectName("ghostButton")
        uninstall_btn.clicked.connect(self.uninstall)
        open_btn = QPushButton("打开目录")
        open_btn.setObjectName("ghostButton")
        open_btn.clicked.connect(self.open_folder)
        detail_btn = QPushButton("详情")
        detail_btn.setObjectName("ghostButton")
        detail_btn.clicked.connect(self.show_detail)
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(reload_btn)
        btn_row.addWidget(market_btn)
        btn_row.addWidget(install_btn)
        btn_row.addWidget(enable_btn)
        btn_row.addWidget(disable_btn)
        btn_row.addWidget(uninstall_btn)
        btn_row.addWidget(open_btn)
        btn_row.addWidget(detail_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.refresh()

    def refresh(self) -> None:
        try:
            skills = self.client.get("/skills")
            self.table.setRowCount(len(skills))
            for i, s in enumerate(skills):
                item = QTableWidgetItem(s.get("name", ""))
                item.setData(256, s.get("id"))
                self.table.setItem(i, 0, item)
                self.table.setItem(i, 1, QTableWidgetItem(s.get("description", "")))
                self.table.setItem(i, 2, QTableWidgetItem(format_package_badge(s.get("package"))))
                status = "启用" if s.get("enabled") else "禁用"
                if not s.get("allowed", True):
                    status += " / 权限受限"
                self.table.setItem(i, 3, QTableWidgetItem(status))
                perms = s.get("permission_summary") or []
                if isinstance(perms, list):
                    perm_text = "; ".join(perms[:3])
                else:
                    perm_text = str(perms)
                self.table.setItem(i, 4, QTableWidgetItem(perm_text))
                kws = ", ".join(s.get("triggers_keywords", [])[:5])
                self.table.setItem(i, 5, QTableWidgetItem(kws))
        except Exception as e:
            QMessageBox.warning(self, "加载失败", str(e))

    def reload(self) -> None:
        try:
            self.client.post("/skills/reload")
            self.refresh()
        except Exception as e:
            QMessageBox.warning(self, "失败", str(e))

    def open_market(self) -> None:
        SkillMarketDialog(self.client, self).exec()

    def install_zip(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择 Skill 安装包", "", "ZIP (*.zip)")
        if not path:
            return
        try:
            self.client.upload("/skills/install", path)
            QMessageBox.information(self, "成功", "Skill 安装完成")
            self.refresh()
        except Exception as e:
            QMessageBox.warning(self, "安装失败", str(e))

    def uninstall(self) -> None:
        sid = self._selected_id()
        if not sid:
            QMessageBox.information(self, "提示", "请先选择一个 Skill")
            return
        reply = QMessageBox.question(self, "确认", f"卸载 Skill {sid}？将移至 disabled 目录。")
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.client.delete(f"/skills/{sid}/uninstall")
            self.refresh()
        except Exception as e:
            QMessageBox.warning(self, "失败", str(e))

    def _selected_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(256) if item else None

    def _toggle(self, enable: bool) -> None:
        sid = self._selected_id()
        if not sid:
            QMessageBox.information(self, "提示", "请先选择一个 Skill")
            return
        action = "enable" if enable else "disable"
        try:
            self.client.post(f"/skills/{sid}/{action}")
            self.refresh()
        except Exception as e:
            QMessageBox.warning(self, "失败", str(e))

    def open_folder(self) -> None:
        try:
            self.client.post("/skills/open-folder")
        except Exception as e:
            QMessageBox.warning(self, "失败", str(e))

    def show_detail(self) -> None:
        sid = self._selected_id()
        if not sid:
            QMessageBox.information(self, "提示", "请先选择一个 Skill")
            return
        SkillDetailDialog(self.client, sid, self).exec()
