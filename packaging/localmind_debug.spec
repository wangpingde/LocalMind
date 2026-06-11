# -*- mode: python ; coding: utf-8 -*-
# Debug build: console=True to capture startup tracebacks.
# Output: dist/LocalMind_debug/LocalMind_debug.exe

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_submodules,
)

PROJECT_ROOT = Path(SPECPATH).resolve().parent  # noqa: F821
APP_DIR = PROJECT_ROOT / "app"

block_cipher = None
datas = []
binaries = []
hiddenimports = []


def _bundle(package_name):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package_name)
    datas.extend(pkg_datas)
    binaries.extend(pkg_binaries)
    hiddenimports.extend(pkg_hidden)


datas.append((str(APP_DIR / "resources"), "app/resources"))

for _pkg in (
    "lancedb",
    "pyarrow",
    "fitz",
    "pptx",
    "docx",
    "openpyxl",
    "tiktoken",
    "tiktoken_ext",
    "keyring",
):
    try:
        _bundle(_pkg)
    except Exception:
        pass

hiddenimports += collect_submodules("uvicorn")
hiddenimports += collect_submodules("encodings")
hiddenimports += [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "anyio._backends._asyncio",
    "sse_starlette",
    "fastapi",
    "starlette",
    "httpx",
    "httpcore",
    "keyring.backends.Windows",
    "win32ctypes.pywin32",
    "win32ctypes.core",
    "pydantic",
    "pydantic_settings",
    "sqlalchemy.dialects.sqlite",
]

datas += collect_data_files("tiktoken_ext", include_py_files=True)


a = Analysis(
    [str(PROJECT_ROOT / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "PyQt5", "PyQt6", "PySide2", "pytest", "notebook"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LocalMind_debug",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="LocalMind_debug",
)
