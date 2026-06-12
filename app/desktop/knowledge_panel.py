"""知识库面板."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.desktop.api_client import ApiClient

from app.desktop.progress_utils import run_knowledge_task

_UPLOAD_FILTER = (
    "文档 (*.txt *.md *.pdf *.docx *.csv *.xlsx *.pptx *.html *.htm *.json "
    "*.py *.java *.sql *.js *.ts *.yaml *.yml);;所有文件 (*.*)"
)
_SUBDIR_ROLE = 256
_BASE_UPLOAD_DIRS = (
    ("inbox", "inbox"),
    ("work", "work"),
    ("personal", "personal"),
)


class KnowledgePanel(QWidget):
    def __init__(self, client: ApiClient) -> None:
        super().__init__()
        self.client = client
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        title = QLabel("知识库")
        title.setObjectName("panelTitle")
        layout.addWidget(title)

        subtitle = QLabel("上传、删除文档并管理本地索引（默认保存到 inbox/）")
        subtitle.setObjectName("panelSubtitle")
        layout.addWidget(subtitle)

        self.stats_label = QLabel("加载中...")
        self.stats_label.setObjectName("statsLabel")
        layout.addWidget(self.stats_label)

        folder_row = QHBoxLayout()
        folder_row.addWidget(QLabel("上传目录"))
        self.folder_combo = QComboBox()
        folder_row.addWidget(self.folder_combo)
        folder_row.addStretch()
        layout.addLayout(folder_row)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["文件名", "路径", "状态", "错误"])
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.table)

        btn_row = QHBoxLayout()
        upload_btn = QPushButton("上传文档")
        upload_btn.setObjectName("primaryButton")
        upload_btn.clicked.connect(self.upload_documents)
        delete_btn = QPushButton("删除文档")
        delete_btn.setObjectName("ghostButton")
        delete_btn.clicked.connect(self.delete_document)
        refresh_btn = QPushButton("刷新")
        refresh_btn.setObjectName("ghostButton")
        refresh_btn.clicked.connect(self.refresh)
        reindex_btn = QPushButton("重新索引")
        reindex_btn.setObjectName("ghostButton")
        reindex_btn.clicked.connect(self.reindex)
        clear_btn = QPushButton("清空索引")
        clear_btn.setObjectName("ghostButton")
        clear_btn.clicked.connect(self.clear_index)
        open_btn = QPushButton("打开目录")
        open_btn.setObjectName("ghostButton")
        open_btn.clicked.connect(self.open_folder)
        btn_row.addWidget(upload_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addWidget(refresh_btn)
        btn_row.addWidget(reindex_btn)
        btn_row.addWidget(clear_btn)
        btn_row.addWidget(open_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        self._action_buttons = [
            upload_btn,
            delete_btn,
            refresh_btn,
            reindex_btn,
            clear_btn,
            open_btn,
        ]

        self._reload_upload_dirs()
        self.refresh()

    def _reload_upload_dirs(self) -> None:
        current = (
            self.folder_combo.currentData(_SUBDIR_ROLE)
            if self.folder_combo.count()
            else "inbox"
        )
        self.folder_combo.blockSignals(True)
        self.folder_combo.clear()
        for label, value in _BASE_UPLOAD_DIRS:
            self.folder_combo.addItem(label, value)

        projects: list[dict] = []
        try:
            projects = self.client.get("/projects") or []
        except Exception:
            projects = []

        active = [p for p in projects if p.get("status", "active") != "inactive"]
        if active:
            self.folder_combo.insertSeparator(self.folder_combo.count())
            for project in active:
                slug = (project.get("slug") or "").strip()
                if not slug:
                    continue
                name = (project.get("name") or slug).strip()
                self.folder_combo.addItem(f"项目: {name}", f"projects/{slug}")

        restore = self.folder_combo.findData(current, _SUBDIR_ROLE)
        self.folder_combo.setCurrentIndex(restore if restore >= 0 else 0)
        self.folder_combo.blockSignals(False)

    def _selected_subdir(self) -> str:
        value = self.folder_combo.currentData(_SUBDIR_ROLE)
        if isinstance(value, str) and value:
            return value
        return self.folder_combo.currentText() or "inbox"

    def refresh(self) -> None:
        self._reload_upload_dirs()
        try:
            data = self.client.get("/knowledge/documents")
            self.stats_label.setText(
                f"路径: {data['knowledge_path']}\n"
                f"文档总数: {data['total']} | 已索引: {data['indexed']} | "
                f"失败: {data['failed']} | 最近索引: {data.get('last_indexed_at') or '-'}"
            )
            docs = data.get("documents", [])
            self.table.setRowCount(len(docs))
            for i, d in enumerate(docs):
                item = QTableWidgetItem(d.get("filename", ""))
                item.setData(256, d.get("id"))
                self.table.setItem(i, 0, item)
                self.table.setItem(i, 1, QTableWidgetItem(d.get("path", "")))
                self.table.setItem(i, 2, QTableWidgetItem(d.get("status", "")))
                err = d.get("error_message") or ""
                err_item = QTableWidgetItem(err)
                if err:
                    err_item.setToolTip(
                        err + ("\n（可能含图片/视频处理失败，请检查视觉模型配置）" if "media" in err.lower() or "vision" in err.lower() else "")
                    )
                self.table.setItem(i, 3, err_item)
        except Exception as e:
            self.stats_label.setText(f"加载失败: {e}")

    def _selected_document_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.data(256) if item else None

    def _set_busy(self, busy: bool) -> None:
        for btn in self._action_buttons:
            btn.setEnabled(not busy)
        self.table.setEnabled(not busy)
        self.folder_combo.setEnabled(not busy)

    def upload_documents(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "选择要上传的文档", "", _UPLOAD_FILTER
        )
        if not paths:
            return

        subdir = self._selected_subdir()
        total = len(paths)
        saved_count = 0
        error_lines: list[str] = []

        def work(report) -> dict:
            merged_saved: list[dict] = []
            merged_errors: list[dict] = []
            for i, path in enumerate(paths, start=1):
                name = path.replace("\\", "/").rsplit("/", 1)[-1]
                report(i, total, f"正在上传并索引 ({i}/{total}): {name}")
                result = self.client.upload_one(
                    "/knowledge/upload",
                    path,
                    params={"subdir": subdir, "reindex": "true"},
                )
                merged_saved.extend(result.get("saved", []))
                merged_errors.extend(result.get("errors", []))
            return {"saved": merged_saved, "errors": merged_errors}

        try:
            self._set_busy(True)
            result = run_knowledge_task(
                self,
                self.client,
                title="上传文档",
                label="正在上传文档...",
                work=work,
                poll_server=True,
            )
            saved_count = len((result or {}).get("saved", []))
            for err in (result or {}).get("errors", []):
                error_lines.append(
                    f"{err.get('filename', '')}: {err.get('message', '')}"
                )
        except Exception as e:
            error_lines.append(str(e))
        finally:
            self._set_busy(False)

        self.refresh()

        if error_lines and saved_count:
            QMessageBox.warning(
                self,
                "部分完成",
                f"成功上传并索引 {saved_count} 个文件。\n\n失败:\n"
                + "\n".join(error_lines[:8]),
            )
        elif error_lines:
            QMessageBox.warning(self, "上传失败", "\n".join(error_lines[:8]))
        else:
            QMessageBox.information(
                self, "完成", f"已上传并索引 {saved_count} 个文档到 {subdir}/"
            )

    def delete_document(self) -> None:
        doc_id = self._selected_document_id()
        if not doc_id:
            QMessageBox.information(self, "提示", "请先选择要删除的文档")
            return

        row = self.table.currentRow()
        name = self.table.item(row, 0).text() if row >= 0 else doc_id
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"确定删除「{name}」？\n将同时删除磁盘文件、切块索引与向量数据。",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            self._set_busy(True)

            def work(_report) -> dict:
                return self.client.delete(
                    f"/knowledge/documents/{doc_id}",
                    timeout=600.0,
                )

            run_knowledge_task(
                self,
                self.client,
                title="删除文档",
                label=f"正在删除「{name}」...",
                work=work,
                poll_server=True,
            )
            self.refresh()
            QMessageBox.information(self, "完成", f"已删除: {name}")
        except Exception as e:
            QMessageBox.warning(self, "删除失败", str(e))
        finally:
            self._set_busy(False)

    def reindex(self) -> None:
        try:
            self._set_busy(True)

            def work(_report) -> dict:
                return self.client.post("/knowledge/reindex", {}, timeout=600.0)

            result = run_knowledge_task(
                self,
                self.client,
                title="重新索引",
                label="正在重建知识库索引，大文档可能需要较长时间...",
                work=work,
                poll_server=True,
            )
            QMessageBox.information(self, "完成", f"索引完成: {(result or {}).get('stats')}")
            self.refresh()
        except Exception as e:
            QMessageBox.warning(self, "失败", str(e))
        finally:
            self._set_busy(False)

    def clear_index(self) -> None:
        reply = QMessageBox.question(self, "确认", "确定清空所有索引？原文件不会被删除。")
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._set_busy(True)

            def work(_report) -> dict:
                return self.client.delete("/knowledge/index", timeout=600.0)

            run_knowledge_task(
                self,
                self.client,
                title="清空索引",
                label="正在清空索引与向量数据...",
                work=work,
                poll_server=True,
            )
            self.refresh()
        except Exception as e:
            QMessageBox.warning(self, "失败", str(e))
        finally:
            self._set_busy(False)

    def open_folder(self) -> None:
        try:
            self.client.post("/knowledge/open-folder")
        except Exception as e:
            QMessageBox.warning(self, "失败", str(e))
