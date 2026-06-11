"""将功能模块拆解为研发任务清单."""
import json
import sys


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

    product = args.get("product") or "Product"
    modules = args.get("modules") or []

    tasks = []
    for mod in modules:
        if isinstance(mod, dict):
            name = mod.get("name") or mod.get("module") or "Module"
            priority = mod.get("priority") or "P1"
            items = mod.get("tasks") or [
                f"设计 {name} 接口",
                f"实现 {name} 核心逻辑",
                f"{name} 联调与测试",
            ]
        else:
            name = str(mod)
            priority = "P1"
            items = [
                f"设计 {name} 接口",
                f"实现 {name} 核心逻辑",
                f"{name} 联调与测试",
            ]
        for i, item in enumerate(items, 1):
            tasks.append(
                {
                    "module": name,
                    "priority": priority,
                    "id": f"{name}-{i}",
                    "title": str(item),
                }
            )

    lines = [f"# 研发任务拆解 — {product}", ""]
    current = ""
    for t in tasks:
        if t["module"] != current:
            current = t["module"]
            lines.extend(["", f"## {current}", ""])
        lines.append(f"- [{t['priority']}] {t['title']} (`{t['id']}`)")

    markdown = "\n".join(lines).strip() + "\n"
    print(
        json.dumps(
            {"status": "ok", "task_count": len(tasks), "tasks": tasks, "markdown": markdown},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
