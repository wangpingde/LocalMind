"""LocalMind 应用入口."""

from __future__ import annotations

import socket
import sys
import threading
import time

from loguru import logger
from PySide6.QtWidgets import QApplication

from app.config.workspace import DEFAULT_PORT, Workspace
from app.desktop.main_window import MainWindow

PORT_SCAN_RANGE = 10
STARTUP_TIMEOUT = 45.0


def _setup_logging(workspace: Workspace) -> None:
    log_file = workspace.logs_dir / "app.log"
    logger.remove()
    # 打包为「无控制台」(console=False) 时 sys.stderr 可能为 None，直接 add 会抛异常
    if sys.stderr is not None:
        logger.add(sys.stderr, level="INFO")
    logger.add(str(log_file), rotation="10 MB", retention="7 days", level="DEBUG")


def _install_excepthook() -> None:
    """把未捕获异常写入日志，避免无控制台打包时崩溃「静默无痕」。"""

    def _hook(exc_type, exc_value, exc_tb):
        logger.opt(exception=(exc_type, exc_value, exc_tb)).critical("未捕获异常导致程序终止")

    sys.excepthook = _hook

    try:
        import threading

        def _thread_hook(args):
            logger.opt(
                exception=(args.exc_type, args.exc_value, args.exc_traceback)
            ).critical("子线程未捕获异常: {}", args.thread.name)

        threading.excepthook = _thread_hook
    except Exception:
        pass


def _start_api_server(port: int) -> None:
    try:
        import uvicorn

        from app.server.api import create_app

        app = create_app()
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    except OSError as e:
        logger.warning("端口 {} 启动失败: {}", port, e)
    except Exception as e:
        logger.exception("本地 API 服务异常退出: {}", e)


def _probe_health(port: int) -> dict | None:
    import httpx

    try:
        resp = httpx.get(f"http://127.0.0.1:{port}/api/health", timeout=2.0)
        if resp.status_code == 200:
            return resp.json()
    except Exception:
        pass
    return None


def _is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _wait_for_server(port: int, timeout: float = STARTUP_TIMEOUT) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = _probe_health(port)
        if data and data.get("status") == "ok":
            return True
        time.sleep(0.25)
    return False


def _try_start_server_on_port(port: int) -> bool:
    if _probe_health(port):
        logger.info("复用已有本地 API 服务，端口 {}", port)
        return True

    if _is_port_open(port):
        logger.debug("端口 {} 已占用且不可复用，跳过", port)
        return False

    logger.info("正在启动本地 API 服务，端口 {} ...", port)
    server_thread = threading.Thread(
        target=_start_api_server,
        args=(port,),
        daemon=True,
        name=f"localmind-api-{port}",
    )
    server_thread.start()
    return _wait_for_server(port)


def _ensure_api_server(preferred_port: int) -> int | None:
    """返回可用端口；失败返回 None."""
    for offset in range(PORT_SCAN_RANGE):
        port = preferred_port + offset
        if _try_start_server_on_port(port):
            if offset > 0:
                logger.warning(
                    "默认端口 {} 不可用，已自动切换到 {}",
                    preferred_port,
                    port,
                )
            return port
    return None


def main() -> None:
    workspace = Workspace()
    workspace.ensure()
    _setup_logging(workspace)
    _install_excepthook()

    settings_port = DEFAULT_PORT
    try:
        import yaml

        app_yaml = workspace.config_dir / "app.yaml"
        if app_yaml.exists():
            data = yaml.safe_load(app_yaml.read_text(encoding="utf-8")) or {}
            settings_port = int(data.get("api_port", DEFAULT_PORT))
    except Exception:
        pass

    actual_port = _ensure_api_server(settings_port)
    if actual_port is None:
        logger.error("本地 API 服务启动失败")
        print("错误: 本地 API 服务启动失败。")
        print(f"  已尝试端口 {settings_port} ~ {settings_port + PORT_SCAN_RANGE - 1}，均不可用。")
        print("  请关闭残留的 LocalMind / Python 进程后重试。")
        print("  也可执行: netstat -ano | findstr \":17777\"")
        print(f"  详细日志: {workspace.logs_dir / 'app.log'}")
        sys.exit(1)

    logger.info("本地 API 服务已就绪，端口 {}", actual_port)

    logger.info("正在创建 Qt 应用 ...")
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("LocalMind")
    logger.info(
        "Qt 平台插件: {}", qt_app.platformName() or "(未知)"
    )

    from app.desktop.theme import apply_theme

    apply_theme(qt_app)
    logger.info("主题已应用，正在构建主窗口 ...")

    window = MainWindow(api_port=actual_port)
    logger.info("主窗口已构建，正在显示 ...")
    window.show()
    _ensure_window_visible(window)
    logger.info("主窗口已显示，进入事件循环")
    sys.exit(qt_app.exec())


def _ensure_window_visible(window) -> None:
    """确保窗口落在可见的屏幕区域内，并置顶激活。

    解决「进程在运行、日志正常，但看不到界面」的常见原因：
    窗口被放到了已断开的副屏 / 屏幕外坐标，或被其他窗口挡住、最小化。
    """
    try:
        from PySide6.QtGui import QGuiApplication

        screen = window.screen() or QGuiApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            frame = window.frameGeometry()
            # 若窗口与任何可见屏幕都没有交集，则移动到主屏中央
            on_screen = any(
                s.availableGeometry().intersects(frame)
                for s in QGuiApplication.screens()
            )
            if not on_screen:
                logger.warning(
                    "窗口位于屏幕可见区域之外 {}，已重置到主屏中央", frame
                )
                frame.moveCenter(available.center())
                window.move(frame.topLeft())
    except Exception as e:
        logger.warning("窗口可见性校正失败: {}", e)

    # 取消最小化、置顶并激活，避免窗口在其他窗口背后
    try:
        from PySide6.QtCore import Qt

        window.setWindowState(
            window.windowState() & ~Qt.WindowState.WindowMinimized
            | Qt.WindowState.WindowActive
        )
        window.show()
        window.raise_()
        window.activateWindow()
    except Exception as e:
        logger.warning("窗口置顶激活失败: {}", e)


if __name__ == "__main__":
    main()
