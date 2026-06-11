"""预览目录文件统计，供整理前评估规模."""
import json
import sys
from collections import Counter
from pathlib import Path


def _load_args() -> dict:
    if not sys.stdin.isatty():
        raw = sys.stdin.read()
        if raw.strip():
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return {}
    if len(sys.argv) > 1:
        try:
            return json.loads(sys.argv[1])
        except json.JSONDecodeError:
            return {}
    return {}


def main() -> int:
    args = _load_args()

    root = Path(args.get("directory", ".")).resolve()
    if not root.is_dir():
        print(json.dumps({"status": "error", "message": f"目录不存在: {root}"}))
        return 1

    exts: Counter[str] = Counter()
    total = 0
    for path in root.rglob("*"):
        if path.is_file():
            total += 1
            exts[path.suffix.lower() or "(无扩展名)"] += 1

    payload = {
        "status": "ok",
        "directory": str(root),
        "total_files": total,
        "by_extension": dict(exts.most_common(20)),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
