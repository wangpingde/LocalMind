"""知识库索引任务进度（供 API 轮询与桌面端进度条）."""

from __future__ import annotations

import threading
from dataclasses import dataclass

_lock = threading.Lock()


@dataclass
class _ProgressState:
    active: bool = False
    operation: str = ""
    current: int = 0
    total: int = 0
    message: str = ""


_state = _ProgressState()


def begin(operation: str, *, total: int = 0, message: str = "") -> None:
    with _lock:
        _state.active = True
        _state.operation = operation
        _state.total = max(total, 0)
        _state.current = 0
        _state.message = message


def step(*, current: int | None = None, message: str = "") -> None:
    with _lock:
        if current is not None:
            _state.current = current
        if message:
            _state.message = message


def finish() -> None:
    with _lock:
        _state.active = False
        _state.operation = ""
        _state.current = 0
        _state.total = 0
        _state.message = ""


def snapshot() -> dict:
    with _lock:
        percent = None
        if _state.total > 0:
            percent = min(100, int(100 * _state.current / _state.total))
        return {
            "active": _state.active,
            "operation": _state.operation,
            "current": _state.current,
            "total": _state.total,
            "message": _state.message,
            "percent": percent,
        }
