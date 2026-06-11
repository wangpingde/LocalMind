# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置（Windows，onedir）。

用法（在项目根目录执行）：
    pyinstaller packaging/localmind.spec --noconfirm --clean

产物：
    dist/LocalMind/LocalMind.exe
"""

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_submodules,
)

# spec 运行时没有 __file__，使用 SPECPATH 定位项目根目录
PROJECT_ROOT = Path(SPECPATH).resolve().parent  # noqa: F821
APP_DIR = PROJECT_ROOT / "app"

block_cipher = None

datas = []
binaries = []
hiddenimports = []


def _bundle(package_name: str) -> None:
    """collect_all 收集某个包的 py 模块 / 数据 / 动态库。"""
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package_name)
    datas.extend(pkg_datas)
    binaries.extend(pkg_binaries)
    hiddenimports.extend(pkg_hidden)


# ── 应用自带资源（Skill 模板、市场包等）──
datas.append((str(APP_DIR / "resources"), "app/resources"))

# ── 含原生库 / 动态导入的第三方包，整体收集 ──
for _pkg in (
    "lancedb",
    "pyarrow",
    "fitz",          # pymupdf
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
        # 某些包未安装或无需收集时忽略
        pass

# ── 仅需补充隐藏导入的包 ──
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
    # keyring Windows 后端（动态加载）
    "keyring.backends.Windows",
    "win32ctypes.pywin32",
    "win32ctypes.core",
    # pydantic / sqlalchemy 动态子模块
    "pydantic",
    "pydantic_settings",
    "sqlalchemy.dialects.sqlite",
]

# tiktoken 的编码注册通过命名空间包 tiktoken_ext 动态发现
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
    excludes=[
        "tkinter",
        "matplotlib",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "pytest",
        "notebook",
    ],
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
    name="LocalMind",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
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
    name="LocalMind",
)
