"""Skill 展示与上下文格式化."""

from __future__ import annotations

from typing import Any

from app.config.app_config import AppSettings
from app.core.skills.skill import Skill
from app.security.permission_checker import PermissionChecker


def package_summary(skill: Skill) -> dict[str, Any]:
    pkg = skill.package
    return {
        "has_references": bool(pkg.references_text),
        "agents_count": len(pkg.agents),
        "scripts_count": len(pkg.scripts),
        "assets_count": len(pkg.assets),
    }


def enrich_skill_dict(
    skill: Skill,
    permission_checker: PermissionChecker,
    settings: AppSettings,
) -> dict[str, Any]:
    data = skill.to_dict()
    data["package"] = package_summary(skill)
    data["allowed"] = permission_checker.is_skill_allowed(
        skill, settings, write_audit=False
    )
    data["permission_summary"] = permission_checker.summarize_permissions(skill)[
        "summary"
    ]
    return data


def format_package_badge(pkg: dict[str, Any] | None) -> str:
    if not pkg:
        return "-"
    parts: list[str] = []
    if pkg.get("agents_count", 0):
        parts.append(f"{pkg['agents_count']} agent")
    if pkg.get("scripts_count", 0):
        parts.append(f"{pkg['scripts_count']} 脚本")
    if pkg.get("assets_count", 0):
        parts.append(f"{pkg['assets_count']} 资产")
    if pkg.get("has_references"):
        parts.append("参考资料")
    return " · ".join(parts) if parts else "仅指令"


def format_used_skills_context(
    skills: list[dict[str, Any]],
    agent_steps: list[dict[str, Any]] | None = None,
) -> str:
    if not skills:
        return "未启用 Skill"

    skill_tools = {
        "list_skill_resources",
        "read_skill_asset",
        "run_skill_script",
    }
    tool_calls: dict[str, list[str]] = {}
    for step in agent_steps or []:
        if step.get("step_type") != "tool_call":
            continue
        tool = step.get("tool") or ""
        if tool not in skill_tools:
            continue
        args = step.get("arguments") or {}
        sid = str(args.get("skill_id") or "")
        if sid:
            tool_calls.setdefault(sid, []).append(tool)

    parts: list[str] = []
    for skill in skills:
        sid = skill.get("id", "")
        name = skill.get("name", "")
        parts.append(f"▸ {name} (`{sid}`)")
        if skill.get("description"):
            parts.append(f"  {skill['description']}")
        pkg = skill.get("package")
        badge = format_package_badge(pkg)
        if badge != "-":
            parts.append(f"  资源: {badge}")

        agents = skill.get("agents") or []
        if agents:
            names = ", ".join(a.get("name", "") for a in agents if a.get("name"))
            parts.append(f"  子 Agent: {names}")

        scripts = skill.get("scripts") or []
        if scripts:
            files = ", ".join(s.get("filename", "") for s in scripts if s.get("filename"))
            parts.append(f"  脚本: {files}")

        assets = skill.get("assets") or []
        if assets:
            paths = ", ".join(a.get("path", "") for a in assets[:5] if a.get("path"))
            if len(assets) > 5:
                paths += f" …共 {len(assets)} 个"
            parts.append(f"  资产: {paths}")

        perms = skill.get("permission_summary")
        if isinstance(perms, list) and perms:
            parts.append("  权限: " + "; ".join(perms[:4]))
        elif skill.get("permissions"):
            parts.append("  权限: 已声明（见 Skill 配置）")

        called = tool_calls.get(sid) or []
        if called:
            parts.append(f"  本次调用: {', '.join(dict.fromkeys(called))}")

        parts.append("")

    return "\n".join(parts).rstrip()
