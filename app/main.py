"""LocalMind 应用入口."""

from __future__ import annotations

import multiprocessing
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
    # 打包为无控制台(windowed)程序时 sys.stderr / sys.stdout 为 None，
    # 直接 logger.add(None) 会抛异常导致启动即崩溃，这里做保护。
    if sys.stderr is not None:
        logger.add(sys.stderr, level="INFO")
    logger.add(str(log_file), rotation="10 MB", retention="7 days", level="DEBUG")


def _start_api_server(port: int) -> None:
    try:
        import uvicorn

        from app.server.api import create_app

        app = create_app()
        # log_config=None：避免 uvicorn 默认日志配置向 stdout/stderr 写入，
        # 在无控制台(windowed)打包环境下 stdout/stderr 为 None 会报错。
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            log_config=None,
        )
    except OSError as e:
        logger.warning("端口 {} 启动失败: {}", port, e)
    except Exception as e:
        logger.exception("本地 API 服务异常退出: {}", e)


def _probe_health(port: int) -> dict | None:
    import httpx

    try:
        # trust_env=False：本地回环请求绝不走系统代理，
        # 避免同事机器上的代理软件（Clash/V2Ray 等）劫持 127.0.0.1 导致健康检查卡死
        resp = httpx.get(
            f"http://127.0.0.1:{port}/api/health", timeout=2.0, trust_env=False
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.debug("健康检查端口 {} 失败: {}", port, e)
    return None


def _is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _wait_for_server(port: int, timeout: float = STARTUP_TIMEOUT) -> bool:
    deadline = time.time() + timeout
    last_log = 0.0
    while time.time() < deadline:
        data = _probe_health(port)
        if data and data.get("status") == "ok":
            return True
        now = time.time()
        if now - last_log >= 5.0:
            logger.info(
                "等待本地 API 健康检查就绪 (端口 {}，已等待 {:.0f}s/{:.0f}s) ...",
                port,
                timeout - (deadline - now),
                timeout,
            )
            last_log = now
        time.sleep(0.25)
    logger.warning(
        "端口 {} 健康检查在 {:.0f}s 内未通过；若本机使用了系统代理，"
        "请确认 127.0.0.1/localhost 已加入代理排除列表（NO_PROXY）",
        port,
        timeout,
    )
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

    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("LocalMind")

    from app.desktop.theme import apply_theme

    apply_theme(qt_app)

    window = MainWindow(api_port=actual_port)
    window.show()
    sys.exit(qt_app.exec())


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
