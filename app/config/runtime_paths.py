"""Runtime path helpers for source and frozen application layouts."""

from __future__ import annotations

import sys
from pathlib import Path


def app_base_dir() -> Path:
    """Return the application root in source or PyInstaller runtime."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    if getattr(sys, "frozen", False) and frozen_root:
        return Path(frozen_root).resolve()
    return Path(__file__).resolve().parents[2]


def app_resource_path(*parts: str) -> Path:
    """Return a path under bundled application resources."""
    return app_base_dir() / "app" / "resources" / Path(*parts)
