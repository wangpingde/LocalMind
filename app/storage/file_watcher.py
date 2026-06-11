"""知识库文件监听."""

from __future__ import annotations

import threading
import time
from pathlib import Path

from loguru import logger
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from app.core.rag.indexer import DocumentIndexer
from app.core.rag.parser import DocParser


class KnowledgeEventHandler(FileSystemEventHandler):
    def __init__(self, indexer: DocumentIndexer) -> None:
        self.indexer = indexer
        self._pending: set[str] = set()
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None

    def on_created(self, event) -> None:
        if not event.is_directory:
            self._schedule(event.src_path)

    def on_modified(self, event) -> None:
        if not event.is_directory:
            self._schedule(event.src_path)

    def on_deleted(self, event) -> None:
        if not event.is_directory:
            self._schedule_remove(event.src_path)

    def on_moved(self, event) -> None:
        if event.is_directory:
            return
        self._schedule_remove(event.src_path)
        if Path(event.dest_path).exists():
            self._schedule(event.dest_path)

    def _schedule_remove(self, path: str) -> None:
        p = Path(path)
        if p.suffix.lower() not in DocParser.SUPPORTED:
            return
        with self._lock:
            self._pending.discard(path)
            if self._timer:
                self._timer.cancel()
                self._timer = None
        try:
            self.indexer.remove_file(p)
        except Exception as e:
            logger.error("自动清理索引失败 {}: {}", path, e)

    def _schedule(self, path: str) -> None:
        p = Path(path)
        if p.suffix.lower() not in DocParser.SUPPORTED:
            return
        with self._lock:
            self._pending.add(path)
            if self._timer:
                self._timer.cancel()
            self._timer = threading.Timer(2.0, self._process_pending)
            self._timer.start()

    def _process_pending(self) -> None:
        with self._lock:
            paths = list(self._pending)
            self._pending.clear()
        for path in paths:
            try:
                self.indexer.index_file(Path(path))
            except Exception as e:
                logger.error("自动索引失败 {}: {}", path, e)


class FileWatcher:
    def __init__(self, knowledge_dir: Path, indexer: DocumentIndexer) -> None:
        self.knowledge_dir = knowledge_dir
        self.indexer = indexer
        self._observer: Observer | None = None

    def start(self) -> None:
        handler = KnowledgeEventHandler(self.indexer)
        self._observer = Observer()
        self._observer.schedule(handler, str(self.knowledge_dir), recursive=True)
        self._observer.start()
        logger.info("文件监听已启动: {}", self.knowledge_dir)

    def stop(self) -> None:
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
