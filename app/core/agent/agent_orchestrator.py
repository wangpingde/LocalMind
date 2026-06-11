"""Agent 多步骤任务编排."""

from __future__ import annotations

import json
from collections.abc import Generator
from dataclasses import dataclass, field
from typing import Any

from app.config.app_config import AppSettings
from app.core.llm.model_gateway import ModelGateway
from app.core.llm.reasoning import StreamPart, ToolCall
from app.core.skills.skill import Skill
from app.core.tools.tool_runner import ToolRunner
from app.storage.sqlite_store import SQLiteStore


@dataclass
class AgentStep:
    step_type: str
    content: dict[str, Any]


@dataclass
class AgentLoopResult:
    content: str
    reasoning: str = ""
    steps: list[AgentStep] = field(default_factory=list)
    run_id: str = ""


@dataclass
class _TurnStreamResult:
    reasoning: str = ""
    content: str = ""
    tool_calls: list[ToolCall] | None = None


class AgentOrchestrator:
    TOOL_SYSTEM_APPEND = (
        "\n\n# 工具使用\n"
        "你可以调用提供的工具完成本地文件操作、知识检索和批处理任务。\n"
        "需要读写文件时优先使用工具，不要编造文件内容。\n"
        "批处理前可先用 dry_run=true 预览，确认后再执行。\n"
        "写入 outputs/ 目录存放生成物；整理任务使用 organize_files 或 batch_process_files。"
    )

    def __init__(
        self,
        model_gateway: ModelGateway,
        tool_runner: ToolRunner,
        sqlite: SQLiteStore,
    ) -> None:
        self.model_gateway = model_gateway
        self.tool_runner = tool_runner
        self.sqlite = sqlite

    def run_loop(
        self,
        messages: list[dict],
        *,
        conversation_id: str,
        user_input: str,
        settings: AppSettings,
        skills: list[Skill],
        project_path_prefix: str | None,
        provider_name: str | None,
        tool_schemas: list[dict],
        max_steps: int | None = None,
        on_step: Any | None = None,
    ) -> AgentLoopResult:
        result: AgentLoopResult | None = None
        for event in self.iter_loop(
            messages,
            conversation_id=conversation_id,
            user_input=user_input,
            settings=settings,
            skills=skills,
            project_path_prefix=project_path_prefix,
            provider_name=provider_name,
            tool_schemas=tool_schemas,
            max_steps=max_steps,
        ):
            if event.get("type") == "step" and on_step:
                on_step(
                    AgentStep(
                        event["step_type"],
                        {k: v for k, v in event.items() if k not in ("type", "step_type")},
                    )
                )
            elif event.get("type") == "complete":
                result = event["result"]
        assert result is not None
        return result

    def iter_loop(
        self,
        messages: list[dict],
        *,
        conversation_id: str,
        user_input: str,
        settings: AppSettings,
        skills: list[Skill],
        project_path_prefix: str | None,
        provider_name: str | None,
        tool_schemas: list[dict],
        max_steps: int | None = None,
    ) -> Generator[dict[str, Any], None, None]:
        """逐步产出 step 事件，最后产出 complete 事件."""
        max_steps = max_steps or settings.agent_max_steps
        run = self.sqlite.create_agent_run(conversation_id, user_input)
        steps: list[AgentStep] = []
        working_messages = list(messages)
        if working_messages and working_messages[0].get("role") == "system":
            working_messages[0] = {
                "role": "system",
                "content": working_messages[0]["content"] + self.TOOL_SYSTEM_APPEND,
            }

        final_content = ""
        final_reasoning = ""
        step_index = 0

        for _ in range(max_steps):
            result = yield from self._iter_turn_events(
                working_messages,
                provider_name=provider_name,
                tool_schemas=tool_schemas,
            )
            if result is None:
                break

            if result.reasoning:
                step = AgentStep("reasoning", {"text": result.reasoning})
                steps.append(step)
                self.sqlite.add_agent_step(run.id, step_index, "reasoning", step.content)
                step_index += 1

            if result.tool_calls:
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": result.content or None,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments, ensure_ascii=False),
                            },
                        }
                        for tc in result.tool_calls
                    ],
                }
                working_messages.append(assistant_msg)

                for tc in result.tool_calls:
                    call_step = AgentStep(
                        "tool_call",
                        {"tool": tc.name, "arguments": tc.arguments},
                    )
                    steps.append(call_step)
                    self.sqlite.add_agent_step(run.id, step_index, "tool_call", call_step.content)
                    step_index += 1
                    yield {
                        "type": "step",
                        "step_type": "tool_call",
                        "tool": tc.name,
                        "arguments": tc.arguments,
                    }

                    tool_result = self._invoke_tool(
                        tc,
                        settings=settings,
                        skills=skills,
                        project_path_prefix=project_path_prefix,
                    )
                    result_step = AgentStep(
                        "tool_result", {"tool": tc.name, "result": tool_result}
                    )
                    steps.append(result_step)
                    self.sqlite.add_agent_step(
                        run.id, step_index, "tool_result", result_step.content
                    )
                    step_index += 1
                    yield {
                        "type": "step",
                        "step_type": "tool_result",
                        "tool": tc.name,
                        "result": tool_result,
                    }

                    working_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": ToolRunner.format_tool_result(tool_result),
                        }
                    )
                continue

            final_content = result.content or ""
            final_reasoning = result.reasoning or ""
            answer_step = AgentStep("answer", {"text": final_content})
            steps.append(answer_step)
            self.sqlite.add_agent_step(run.id, step_index, "answer", answer_step.content)
            self.sqlite.finish_agent_run(run.id, "completed")
            yield {
                "type": "complete",
                "result": AgentLoopResult(
                    content=final_content,
                    reasoning=final_reasoning,
                    steps=steps,
                    run_id=run.id,
                ),
            }
            return

        self.sqlite.finish_agent_run(run.id, "max_steps")
        if not final_content:
            final_content = "已达到最大执行步骤，任务可能未完全完成。可缩小任务范围后重试。"
        yield {
            "type": "complete",
            "result": AgentLoopResult(
                content=final_content,
                reasoning=final_reasoning,
                steps=steps,
                run_id=run.id,
            ),
        }

    def _iter_turn_events(
        self,
        messages: list[dict],
        *,
        provider_name: str | None,
        tool_schemas: list[dict],
    ) -> Generator[dict[str, Any], None, _TurnStreamResult | None]:
        """流式调用 LLM，边收边推送 step_delta / chunk."""
        stream = self.model_gateway.chat(
            messages,
            stream=True,
            provider_name=provider_name,
            tools=tool_schemas,
        )
        if not hasattr(stream, "__iter__"):
            return None

        reasoning_parts: list[str] = []
        content_parts: list[str] = []
        tool_calls: list[ToolCall] | None = None

        for part in stream:
            if not isinstance(part, StreamPart):
                continue
            if part.kind == "reasoning" and part.text:
                reasoning_parts.append(part.text)
                yield {
                    "type": "step_delta",
                    "step_type": "reasoning",
                    "text": part.text,
                }
            elif part.kind == "content" and part.text:
                content_parts.append(part.text)
                yield {"type": "chunk", "content": part.text}
            elif part.kind == "tool_call_meta" and part.tool_name:
                yield {
                    "type": "step_delta",
                    "step_type": "tool_call",
                    "tool": part.tool_name,
                    "tool_index": part.tool_index or 0,
                }
            elif part.kind == "tool_call_args" and part.text:
                idx = part.tool_index or 0
                yield {
                    "type": "step_delta",
                    "step_type": "tool_call_args",
                    "tool_index": idx,
                    "text": part.text,
                }
            elif part.kind == "turn_end":
                tool_calls = part.tool_calls

        if tool_calls:
            yield {"type": "answer_reset"}

        return _TurnStreamResult(
            reasoning="".join(reasoning_parts),
            content="" if tool_calls else "".join(content_parts),
            tool_calls=tool_calls,
        )

    def _invoke_tool(
        self,
        tc: ToolCall,
        *,
        settings: AppSettings,
        skills: list[Skill],
        project_path_prefix: str | None,
    ) -> dict[str, Any]:
        result = self.tool_runner.invoke(
            tc.name,
            tc.arguments,
            settings=settings,
            active_skills=skills,
            project_path_prefix=project_path_prefix,
            dry_run=False,
            confirm_overwrite=settings.auto_confirm_file_write,
        )
        if result.get("status") == "needs_confirmation":
            retry = self.tool_runner.invoke(
                tc.name,
                {**tc.arguments, "overwrite": True},
                settings=settings,
                active_skills=skills,
                project_path_prefix=project_path_prefix,
                dry_run=False,
                confirm_overwrite=True,
            )
            return retry
        return result
