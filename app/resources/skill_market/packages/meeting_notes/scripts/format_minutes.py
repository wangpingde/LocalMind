"""将会议 JSON 格式化为标准 Markdown 纪要."""
import json
import sys
from datetime import datetime


def _load_payload() -> dict:
    if not sys.stdin.isatty():
        raw = sys.stdin.read()
        if raw.strip():
            return json.loads(raw)
    if len(sys.argv) > 1:
        return json.loads(sys.argv[1])
    return {}


def main() -> int:
    try:
        payload = _load_payload()
    except json.JSONDecodeError as e:
        print(json.dumps({"status": "error", "message": str(e)}))
        return 1

    title = payload.get("title") or "会议纪要"
    when = payload.get("time") or datetime.now().strftime("%Y-%m-%d")
    participants = payload.get("participants") or []
    topics = payload.get("topics") or []
    todos = payload.get("todos") or []
    risks = payload.get("risks") or []

    lines = [
        f"# 会议纪要 — {title}",
        "",
        f"- 时间：{when}",
        f"- 参与人：{', '.join(participants) if participants else '（待补充）'}",
        "",
        "## 议题与结论",
    ]
    for item in topics:
        if isinstance(item, dict):
            lines.append(f"- **{item.get('topic', '')}**：{item.get('conclusion', '')}")
        else:
            lines.append(f"- {item}")

    lines.extend(["", "## 待办事项（负责人 / 截止日期）"])
    for item in todos:
        if isinstance(item, dict):
            lines.append(
                f"- {item.get('task', '')} — {item.get('owner', '待定')} / {item.get('due', '待定')}"
            )
        else:
            lines.append(f"- {item}")

    lines.extend(["", "## 风险与跟进"])
    for item in risks:
        lines.append(f"- {item}")

    markdown = "\n".join(lines) + "\n"
    print(json.dumps({"status": "ok", "markdown": markdown}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
