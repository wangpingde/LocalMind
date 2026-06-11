"""工具注册表."""

from __future__ import annotations

from typing import Any

from app.core.tools.base import ToolContext, ToolDefinition
from app.core.skills.skill import Skill
from app.core.skills.skill_permissions import allowed_tool_names
from app.core.tools.file_tools import (
    tool_batch_process_files,
    tool_list_files,
    tool_mkdir,
    tool_move_file,
    tool_organize_files,
    tool_read_file,
    tool_search_knowledge,
    tool_write_file,
)
from app.core.tools.skill_tools import (
    tool_list_skill_resources,
    tool_read_skill_asset,
    tool_run_skill_script,
)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._register_builtins()

    def _register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def _register_builtins(self) -> None:
        self._register(
            ToolDefinition(
                name="read_file",
                description="读取工作区内文本文件内容",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "相对工作区的文件路径"},
                    },
                    "required": ["path"],
                },
                handler=tool_read_file,
                requires_read=True,
            )
        )
        self._register(
            ToolDefinition(
                name="write_file",
                description="在工作区 outputs 等允许目录写入文本文件",
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                        "overwrite": {"type": "boolean", "description": "是否覆盖已有文件"},
                    },
                    "required": ["path", "content"],
                },
                handler=tool_write_file,
                requires_write=True,
            )
        )
        self._register(
            ToolDefinition(
                name="list_files",
                description="列出目录中的文件",
                parameters={
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "description": "相对路径，默认 outputs"},
                        "recursive": {"type": "boolean"},
                        "pattern": {"type": "string", "description": "glob 模式，默认 *"},
                    },
                },
                handler=tool_list_files,
                requires_read=True,
            )
        )
        self._register(
            ToolDefinition(
                name="mkdir",
                description="创建目录（含父目录）",
                parameters={
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
                handler=tool_mkdir,
                requires_write=True,
            )
        )
        self._register(
            ToolDefinition(
                name="move_file",
                description="移动或重命名文件",
                parameters={
                    "type": "object",
                    "properties": {
                        "source": {"type": "string"},
                        "destination": {"type": "string"},
                    },
                    "required": ["source", "destination"],
                },
                handler=tool_move_file,
                requires_write=True,
            )
        )
        self._register(
            ToolDefinition(
                name="search_knowledge",
                description="检索本地知识库文档片段",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "top_k": {"type": "integer"},
                    },
                    "required": ["query"],
                },
                handler=tool_search_knowledge,
            )
        )
        self._register(
            ToolDefinition(
                name="organize_files",
                description="整理目录内文件：按扩展名或修改日期分文件夹",
                parameters={
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "description": "要整理的目录"},
                        "strategy": {
                            "type": "string",
                            "enum": ["by_extension", "by_date"],
                        },
                        "dry_run": {"type": "boolean", "description": "仅预览不执行"},
                    },
                    "required": ["directory"],
                },
                handler=tool_organize_files,
                requires_write=True,
            )
        )
        self._register(
            ToolDefinition(
                name="batch_process_files",
                description=(
                    "批处理文件：organize_by_extension、organize_by_date、copy_to、"
                    "rename_batch、merge_text、generate_index"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string",
                            "enum": [
                                "organize_by_extension",
                                "organize_by_date",
                                "copy_to",
                                "rename_batch",
                                "merge_text",
                                "generate_index",
                            ],
                        },
                        "source_dir": {"type": "string"},
                        "source_glob": {"type": "string"},
                        "dest_dir": {"type": "string"},
                        "output_path": {"type": "string"},
                        "pattern": {"type": "string"},
                        "dry_run": {"type": "boolean"},
                        "overwrite": {"type": "boolean"},
                    },
                    "required": ["operation"],
                },
                handler=tool_batch_process_files,
                requires_write=True,
            )
        )
        self._register(
            ToolDefinition(
                name="list_skill_resources",
                description="列出当前激活 Skill 的 agents/scripts/assets 资源清单",
                parameters={
                    "type": "object",
                    "properties": {
                        "skill_id": {
                            "type": "string",
                            "description": "可选，指定 Skill id；省略则列出全部激活 Skill",
                        },
                    },
                },
                handler=tool_list_skill_resources,
            )
        )
        self._register(
            ToolDefinition(
                name="read_skill_asset",
                description="读取 Skill 的 assets/ 目录下的文本资产",
                parameters={
                    "type": "object",
                    "properties": {
                        "skill_id": {"type": "string"},
                        "path": {
                            "type": "string",
                            "description": "相对 assets/ 的路径",
                        },
                    },
                    "required": ["skill_id", "path"],
                },
                handler=tool_read_skill_asset,
                requires_read=True,
            )
        )
        self._register(
            ToolDefinition(
                name="run_skill_script",
                description="执行 Skill 的 scripts/ 目录下脚本（Python/PowerShell 等）",
                parameters={
                    "type": "object",
                    "properties": {
                        "skill_id": {"type": "string"},
                        "script": {"type": "string", "description": "脚本文件名"},
                        "arguments": {
                            "type": "object",
                            "description": "传给脚本的 JSON 参数（Python 为 argv[1]）",
                        },
                    },
                    "required": ["skill_id", "script"],
                },
                handler=tool_run_skill_script,
            )
        )

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def openai_schemas(self) -> list[dict[str, Any]]:
        return [t.to_openai_schema() for t in self._tools.values()]

    def openai_schemas_for(self, skills: list[Skill]) -> list[dict[str, Any]]:
        allowed = allowed_tool_names(skills)
        tools = self.list_tools()
        if allowed is not None:
            tools = [t for t in tools if t.name in allowed]
        return [t.to_openai_schema() for t in tools]

    def execute(
        self, ctx: ToolContext, name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        tool = self.get(name)
        if not tool:
            return {"status": "error", "message": f"未知工具: {name}"}
        try:
            return tool.handler(ctx, arguments)
        except Exception as e:
            return {"status": "error", "message": str(e)}
