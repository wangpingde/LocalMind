"""根据用户问题给出餐饮数字化专家路由建议."""
import json
import sys


PRODUCT_KEYWORDS = {
    "prd",
    "需求",
    "产品",
    "流程",
    "用户旅程",
    "mvp",
    "路线图",
    "验收",
    "指标",
}
TECH_KEYWORDS = {
    "架构",
    "接口",
    "api",
    "数据模型",
    "数据库",
    "稳定性",
    "部署",
    "安全",
    "外卖对接",
    "支付",
}
MARKETING_KEYWORDS = {
    "营销",
    "品牌",
    "活动",
    "会员",
    "私域",
    "复购",
    "拉新",
    "文案",
    "抖音",
    "小红书",
    "roi",
}


def _load_args() -> dict:
    if not sys.stdin.isatty():
        raw = sys.stdin.read()
        if raw.strip():
            return json.loads(raw)
    if len(sys.argv) > 1:
        return json.loads(sys.argv[1])
    return {}


def _match(text: str, keywords: set[str]) -> list[str]:
    lowered = text.lower()
    return sorted(k for k in keywords if k.lower() in lowered)


def main() -> int:
    try:
        args = _load_args()
    except json.JSONDecodeError as e:
        print(json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False))
        return 1

    text = str(args.get("question") or args.get("text") or "")
    matches = {
        "product_architect": _match(text, PRODUCT_KEYWORDS),
        "local_knowledge_qa": _match(text, TECH_KEYWORDS),
        "personal_writer": _match(text, MARKETING_KEYWORDS),
    }
    selected = [skill for skill, words in matches.items() if words]
    if not selected:
        selected = ["restaurant_expert_system"]

    if len(selected) >= 2:
        selected.insert(0, "restaurant_expert_system")

    result = {
        "status": "ok",
        "selected_skills": selected,
        "matches": matches,
        "recommendation": "按产品、技术、营销分工输出，再由总控整合。" if len(selected) > 1 else "先做专家诊断，再补齐关键信息。",
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
