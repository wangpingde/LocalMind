"""本地文件批处理与整理（v0.3 核心能力）."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal


@dataclass
class BatchItemResult:
    source: str
    status: str
    message: str = ""
    target: str = ""


@dataclass
class BatchReport:
    operation: str
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    items: list[BatchItemResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "total": self.total,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "skipped": self.skipped,
            "items": [
                {
                    "source": i.source,
                    "status": i.status,
                    "message": i.message,
                    "target": i.target,
                }
                for i in self.items
            ],
        }


class FileBatchProcessor:
    """高质量本地文件批处理引擎."""

    TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".csv", ".json", ".yaml", ".yml", ".log"}

    def resolve_glob(self, root: Path, pattern: str) -> list[Path]:
        pattern = pattern.replace("\\", "/").strip()
        if pattern.startswith("/"):
            pattern = pattern.lstrip("/")
        base = root
        glob_part = pattern
        if "/" in pattern:
            parent, glob_part = pattern.rsplit("/", 1)
            base = (root / parent).resolve()
        if not base.exists():
            return []
        return sorted(p for p in base.glob(glob_part) if p.is_file())

    def organize_by_extension(
        self,
        source_dir: Path,
        *,
        dry_run: bool = False,
        skip_hidden: bool = True,
    ) -> BatchReport:
        report = BatchReport(operation="organize_by_extension")
        if not source_dir.is_dir():
            report.items.append(
                BatchItemResult(str(source_dir), "failed", "目录不存在")
            )
            report.failed = 1
            report.total = 1
            return report

        for file_path in sorted(source_dir.iterdir()):
            if not file_path.is_file():
                continue
            if skip_hidden and file_path.name.startswith("."):
                continue
            ext = file_path.suffix.lower().lstrip(".") or "no_extension"
            target_dir = source_dir / ext
            target = target_dir / file_path.name
            report.total += 1
            if target.resolve() == file_path.resolve():
                report.skipped += 1
                report.items.append(BatchItemResult(str(file_path), "skipped", "已在目标位置"))
                continue
            if target.exists():
                report.failed += 1
                report.items.append(
                    BatchItemResult(str(file_path), "failed", f"目标已存在: {target.name}")
                )
                continue
            if not dry_run:
                target_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(file_path), str(target))
            report.succeeded += 1
            report.items.append(
                BatchItemResult(str(file_path), "ok", "已整理", str(target.relative_to(source_dir)))
            )
        return report

    def organize_by_date(
        self,
        source_dir: Path,
        *,
        date_format: str = "%Y-%m",
        dry_run: bool = False,
    ) -> BatchReport:
        report = BatchReport(operation="organize_by_date")
        if not source_dir.is_dir():
            report.failed = 1
            report.total = 1
            report.items.append(BatchItemResult(str(source_dir), "failed", "目录不存在"))
            return report

        for file_path in sorted(source_dir.iterdir()):
            if not file_path.is_file() or file_path.name.startswith("."):
                continue
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            bucket = mtime.strftime(date_format)
            target_dir = source_dir / bucket
            target = target_dir / file_path.name
            report.total += 1
            if target.exists() and target.resolve() != file_path.resolve():
                report.failed += 1
                report.items.append(BatchItemResult(str(file_path), "failed", "目标已存在"))
                continue
            if not dry_run:
                target_dir.mkdir(parents=True, exist_ok=True)
                if target.resolve() != file_path.resolve():
                    shutil.move(str(file_path), str(target))
            report.succeeded += 1
            report.items.append(
                BatchItemResult(str(file_path), "ok", bucket, str(target.relative_to(source_dir)))
            )
        return report

    def copy_files(
        self,
        files: list[Path],
        dest_dir: Path,
        *,
        overwrite: bool = False,
        dry_run: bool = False,
    ) -> BatchReport:
        report = BatchReport(operation="copy_files")
        if not dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)
        for src in files:
            report.total += 1
            dest = dest_dir / src.name
            if dest.exists() and not overwrite:
                report.skipped += 1
                report.items.append(BatchItemResult(str(src), "skipped", "目标已存在"))
                continue
            try:
                if not dry_run:
                    shutil.copy2(src, dest)
                report.succeeded += 1
                report.items.append(BatchItemResult(str(src), "ok", "已复制", str(dest)))
            except OSError as e:
                report.failed += 1
                report.items.append(BatchItemResult(str(src), "failed", str(e)))
        return report

    def rename_batch(
        self,
        files: list[Path],
        pattern: str = "{stem}_{index:03d}{suffix}",
        *,
        dry_run: bool = False,
    ) -> BatchReport:
        report = BatchReport(operation="rename_batch")
        for index, src in enumerate(files, 1):
            report.total += 1
            new_name = pattern.format(
                stem=src.stem,
                suffix=src.suffix,
                index=index,
                name=src.name,
            )
            dest = src.with_name(new_name)
            if dest.exists() and dest != src:
                report.failed += 1
                report.items.append(BatchItemResult(str(src), "failed", f"重名: {new_name}"))
                continue
            if not dry_run and dest != src:
                src.rename(dest)
            report.succeeded += 1
            report.items.append(BatchItemResult(str(src), "ok", "已重命名", str(dest.name)))
        return report

    def merge_text_files(
        self,
        files: list[Path],
        output_path: Path,
        *,
        separator: str = "\n\n---\n\n",
        include_header: bool = True,
        dry_run: bool = False,
    ) -> BatchReport:
        report = BatchReport(operation="merge_text_files")
        text_files = [f for f in files if f.suffix.lower() in self.TEXT_SUFFIXES]
        report.total = len(text_files)
        if not text_files:
            report.failed = 1
            report.items.append(BatchItemResult("", "failed", "没有可合并的文本文件"))
            return report

        parts: list[str] = []
        for fp in text_files:
            try:
                content = fp.read_text(encoding="utf-8", errors="replace").strip()
                if include_header:
                    parts.append(f"# {fp.name}\n\n{content}")
                else:
                    parts.append(content)
                report.succeeded += 1
                report.items.append(BatchItemResult(str(fp), "ok", "已合并"))
            except OSError as e:
                report.failed += 1
                report.items.append(BatchItemResult(str(fp), "failed", str(e)))

        if not dry_run and parts:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(separator.join(parts), encoding="utf-8")
        return report

    def generate_directory_index(
        self,
        source_dir: Path,
        output_path: Path,
        *,
        recursive: bool = False,
        dry_run: bool = False,
    ) -> BatchReport:
        report = BatchReport(operation="generate_directory_index")
        if not source_dir.is_dir():
            report.failed = 1
            report.total = 1
            report.items.append(BatchItemResult(str(source_dir), "failed", "目录不存在"))
            return report

        iterator = source_dir.rglob("*") if recursive else source_dir.iterdir()
        entries: list[str] = [f"# 目录索引: {source_dir.name}", ""]
        count = 0
        for path in sorted(iterator):
            if path.name.startswith("."):
                continue
            if path.is_file():
                count += 1
                stat = path.stat()
                rel = path.relative_to(source_dir)
                size_kb = stat.st_size / 1024
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                entries.append(f"- `{rel}` — {size_kb:.1f} KB, 修改于 {mtime}")
        report.total = count
        report.succeeded = count
        content = "\n".join(entries) + "\n"
        if not dry_run:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
        report.items.append(
            BatchItemResult(str(source_dir), "ok", f"索引 {count} 个文件", str(output_path))
        )
        return report

    def batch_process(
        self,
        root: Path,
        operation: Literal[
            "organize_by_extension",
            "organize_by_date",
            "copy_to",
            "rename_batch",
            "merge_text",
            "generate_index",
        ],
        *,
        source_glob: str = "*",
        source_dir: str = "",
        dest_dir: str = "",
        output_path: str = "",
        pattern: str = "{stem}_{index:03d}{suffix}",
        dry_run: bool = False,
        overwrite: bool = False,
        recursive_index: bool = False,
    ) -> BatchReport:
        """统一批处理入口."""
        base_dir = (root / source_dir).resolve() if source_dir else root

        if operation == "organize_by_extension":
            return self.organize_by_extension(base_dir, dry_run=dry_run)
        if operation == "organize_by_date":
            return self.organize_by_date(base_dir, dry_run=dry_run)
        if operation == "generate_index":
            out = (root / output_path).resolve() if output_path else base_dir / "INDEX.md"
            return self.generate_directory_index(
                base_dir, out, recursive=recursive_index, dry_run=dry_run
            )

        files = self.resolve_glob(root, source_glob) if source_glob else []
        if operation == "copy_to":
            dest = (root / dest_dir).resolve()
            return self.copy_files(files, dest, overwrite=overwrite, dry_run=dry_run)
        if operation == "rename_batch":
            return self.rename_batch(files, pattern=pattern, dry_run=dry_run)
        if operation == "merge_text":
            out = (root / output_path).resolve() if output_path else base_dir / "merged.md"
            return self.merge_text_files(files, out, dry_run=dry_run)

        report = BatchReport(operation=operation)
        report.failed = 1
        report.total = 1
        report.items.append(BatchItemResult("", "failed", f"未知操作: {operation}"))
        return report


def safe_relative(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def normalize_rel_path(path_str: str) -> str:
    return path_str.replace("\\", "/").strip().lstrip("/")
