"""汇总检索来源，生成引用清单 JSON."""
import json
import sys
from collections import OrderedDict


def _load_args() -> dict:
    if not sys.stdin.isatty():
        raw = sys.stdin.read()
        if raw.strip():
            return json.loads(raw)
    if len(sys.argv) > 1:
        return json.loads(sys.argv[1])
    return {}


def main() -> int:
    try:
        args = _load_args()
    except json.JSONDecodeError as e:
        print(json.dumps({"status": "error", "message": str(e)}))
        return 1

    sources = args.get("sources") or []
    grouped: OrderedDict[str, list[str]] = OrderedDict()
    for item in sources:
        if isinstance(item, dict):
            name = str(item.get("filename") or item.get("path") or "unknown")
            snippet = str(item.get("snippet") or item.get("content") or "")[:120]
        else:
            name = str(item)
            snippet = ""
        grouped.setdefault(name, [])
        if snippet and snippet not in grouped[name]:
            grouped[name].append(snippet)

    payload = {
        "status": "ok",
        "query": args.get("query", ""),
        "source_count": len(grouped),
        "sources": [
            {"filename": k, "snippets": v, "citation": f"[{k}]"}
            for k, v in grouped.items()
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
