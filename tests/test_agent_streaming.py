"""Agent 流式事件测试."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.core.agent.agent_orchestrator import AgentOrchestrator
from app.core.llm.reasoning import StreamPart, ToolCall


def test_iter_turn_events_yield_incrementally():
    gateway = MagicMock()
    gateway.chat.return_value = iter(
        [
            StreamPart(kind="reasoning", text="思"),
            StreamPart(kind="reasoning", text="考"),
            StreamPart(kind="content", text="答"),
            StreamPart(kind="turn_end", tool_calls=None),
        ]
    )
    orch = AgentOrchestrator(gateway, MagicMock(), MagicMock())

    gen = orch._iter_turn_events([], provider_name="p", tool_schemas=[])
    first = next(gen)
    second = next(gen)
    third = next(gen)

    assert first == {"type": "step_delta", "step_type": "reasoning", "text": "思"}
    assert second == {"type": "step_delta", "step_type": "reasoning", "text": "考"}
    assert third == {"type": "chunk", "content": "答"}

    try:
        next(gen)
        assert False, "generator should stop after return"
    except StopIteration as exc:
        result = exc.value
        assert result.reasoning == "思考"
        assert result.content == "答"
        assert result.tool_calls is None


def test_iter_turn_events_answer_reset_on_tools():
    gateway = MagicMock()
    tool = ToolCall(id="c1", name="list_dir", arguments={"path": "."})
    gateway.chat.return_value = iter(
        [
            StreamPart(kind="content", text="误"),
            StreamPart(kind="turn_end", tool_calls=[tool]),
        ]
    )
    orch = AgentOrchestrator(gateway, MagicMock(), MagicMock())
    gen = orch._iter_turn_events([], provider_name="p", tool_schemas=[])

    chunk = next(gen)
    reset = next(gen)
    assert chunk == {"type": "chunk", "content": "误"}
    assert reset == {"type": "answer_reset"}

    try:
        next(gen)
        assert False
    except StopIteration as exc:
        assert exc.value.tool_calls == [tool]
        assert exc.value.content == ""
