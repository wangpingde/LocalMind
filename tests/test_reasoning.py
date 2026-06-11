"""Reasoning 解析测试."""

from app.core.llm.reasoning import (
    merge_chat_result,
    parse_assistant_message,
    serialize_assistant_message,
    split_think_tags,
)


def test_split_think_tags():
    tag = "think"
    open_tag, close_tag = f"<{tag}>", f"</{tag}>"
    text = f"{open_tag}第一步分析{close_tag}\n\n这是最终回答"
    reasoning, answer = split_think_tags(text)
    assert "第一步" in reasoning
    assert "最终回答" in answer
    assert open_tag not in answer


def test_serialize_and_parse():
    raw = serialize_assistant_message("回答正文", "思考内容")
    reasoning, answer, steps = parse_assistant_message(raw)
    assert reasoning == "思考内容"
    assert answer == "回答正文"
    assert steps == []


def test_serialize_agent_steps():
    steps = [{"step_type": "reasoning", "text": "分析中"}]
    raw = serialize_assistant_message("完成", agent_steps=steps)
    _, answer, parsed = parse_assistant_message(raw)
    assert answer == "完成"
    assert parsed[0]["step_type"] == "reasoning"


def test_merge_chat_result():
    result = merge_chat_result("正文", "api思考")
    assert result.reasoning == "api思考"
    assert result.content == "正文"
