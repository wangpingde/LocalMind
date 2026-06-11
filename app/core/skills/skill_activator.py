"""Skill 激活：组装完整上下文（非仅拼接正文）."""

from __future__ import annotations

from app.core.skills.skill import Skill
from app.core.skills.skill_permissions import allowed_tool_names


class SkillActivator:
    def build_sections(self, skills: list[Skill]) -> str:
        if not skills:
            return ""
        parts = ["# Active Skills"]
        for skill in skills:
            parts.append(self._format_skill(skill))
        return "\n".join(parts)

    def _format_skill(self, skill: Skill) -> str:
        pkg = skill.package
        lines = [
            f"\n## {skill.name} (`{skill.id}`)",
            f"版本 {skill.version} · {skill.description}",
            "\n### 工作指令",
            pkg.body or skill.prompt,
        ]

        if pkg.agents:
            lines.append("\n### 子 Agent 流程 (agents/)")
            for agent in pkg.agents:
                lines.append(f"\n**{agent.name}** — {agent.description}")
                if agent.instructions:
                    lines.append(agent.instructions)
                if agent.tools:
                    lines.append(f"建议工具: {', '.join(agent.tools)}")

        if pkg.references_text:
            lines.append("\n### 参考资料 (references/)")
            lines.append(pkg.references_text)

        if pkg.assets:
            lines.append("\n### 可用资产 (assets/)")
            lines.append("使用 `read_skill_asset` 读取以下内容：")
            for asset in pkg.assets:
                kb = asset.size / 1024
                lines.append(f"- `{asset.rel_path}` ({kb:.1f} KB)")

        if pkg.scripts:
            lines.append("\n### 可执行脚本 (scripts/)")
            lines.append("使用 `run_skill_script` 调用（需开启 Shell/脚本权限）：")
            for script in pkg.scripts:
                desc = f" — {script.description}" if script.description else ""
                lines.append(f"- `{script.filename}`{desc}")

        allowed = allowed_tool_names([skill])
        perms = skill.permissions or {}
        lines.append("\n### 权限与工具")
        if allowed is None:
            lines.append("- 工具: 全部内置工具 + Skill 扩展工具")
        else:
            lines.append(f"- 允许工具: {', '.join(sorted(allowed))}")
        for key, label in (
            ("file_read", "可读路径"),
            ("file_write", "可写路径"),
        ):
            paths = perms.get(key)
            if paths:
                if isinstance(paths, list):
                    lines.append(f"- {label}: {', '.join(paths)}")
                else:
                    lines.append(f"- {label}: {paths}")
        net = perms.get("network")
        if isinstance(net, dict) and net.get("enabled"):
            lines.append("- 网络: 已声明（需全局开启）")
        shell = perms.get("shell") or perms.get("scripts")
        if shell and (shell is True or (isinstance(shell, dict) and shell.get("enabled"))):
            lines.append("- 脚本/Shell: 已声明（需全局开启）")

        return "\n".join(lines)
