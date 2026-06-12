"""桌面端长时间任务进度对话框."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QEventLoop, QObject, QThread, Qt, Signal
from PySide6.QtWidgets import QProgressDialog, QWidget

from app.desktop.api_client import ApiClient

_KNOWLEDGE_TIMEOUT = 600.0


class _TaskWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)
    progress = Signal(int, int, str)

    def __init__(self, fn: Callable[..., Any], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            result = self._fn(self._emit_progress)
            self.finished_ok.emit(result)
        except Exception as e:
            self.failed.emit(str(e))

    def _emit_progress(self, current: int, total: int, message: str) -> None:
        self.progress.emit(current, total, message)


def run_knowledge_task(
    parent: QWidget,
    client: ApiClient,
    *,
    title: str,
    label: str,
    work: Callable[..., Any],
    poll_server: bool = True,
) -> Any:
    """在后台线程执行任务，显示进度条；可选轮询 /knowledge/progress。"""
    dialog = QProgressDialog(label, None, 0, 0, parent)
    dialog.setWindowTitle(title)
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    dialog.setMinimumDuration(0)
    dialog.setMinimumWidth(420)
    dialog.setAutoClose(False)
    dialog.setAutoReset(False)
    dialog.setCancelButton(None)
    dialog.setRange(0, 0)

    loop = QEventLoop()
    result: dict[str, Any] = {}

    worker = _TaskWorker(work, parent)

    def on_progress(current: int, total: int, message: str) -> None:
        if total > 0:
            dialog.setRange(0, total)
            dialog.setValue(min(current, total))
        else:
            dialog.setRange(0, 0)
        if message:
            dialog.setLabelText(message)

    def on_ok(data: object) -> None:
        result["data"] = data
        loop.quit()

    def on_fail(msg: str) -> None:
        result["error"] = msg
        loop.quit()

    worker.progress.connect(on_progress)
    worker.finished_ok.connect(on_ok)
    worker.failed.connect(on_fail)

    timer = None
    if poll_server:
        from PySide6.QtCore import QTimer

        timer = QTimer(parent)

        def poll() -> None:
            try:
                p = client.get("/knowledge/progress")
                if not p.get("active"):
                    return
                total = int(p.get("total") or 0)
                current = int(p.get("current") or 0)
                message = p.get("message") or label
                on_progress(current, total, message)
            except Exception:
                pass

        timer.timeout.connect(poll)
        timer.start(200)

    worker.start()
    dialog.show()
    loop.exec()
    worker.wait()
    if timer:
        timer.stop()
    dialog.close()

    if "error" in result:
        raise RuntimeError(str(result["error"]))
    return result.get("data")
