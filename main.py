"""LocalMind 启动入口."""

import multiprocessing

if __name__ == "__main__":
    # 必须在任何其它导入/线程启动前调用，避免 PyInstaller 冻结后子进程递归启动
    multiprocessing.freeze_support()

    from app.main import main

    main()
