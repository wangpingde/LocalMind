"""根据主题与要点生成 Markdown 大纲."""
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

    title = args.get("title") or "文稿"
    style = args.get("style") or "formal"
    points = args.get("points") or []

    lines = [f"# {title}", "", f"> 风格: {style}", ""]
    for i, point in enumerate(points, 1):
        if isinstance(point, dict):
            heading = point.get("heading") or f"章节 {i}"
            bullets = point.get("bullets") or []
        else:
            heading = str(point)
            bullets = []
        lines.append(f"## {heading}")
        for b in bullets:
            lines.append(f"- {b}")
        if not bullets:
            lines.append("- （待展开）")
        lines.append("")

    markdown = "\n".join(lines).rstrip() + "\n"
    print(json.dumps({"status": "ok", "markdown": markdown}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
