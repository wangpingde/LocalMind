"""记忆抽取解析测试."""

from app.core.memory.memory_extractor import parse_extraction_response


def test_parse_empty_array() -> None:
    assert parse_extraction_response("[]") == []


def test_parse_json_array() -> None:
    raw = """[
        {"type": "preference", "content": "用户偏好简洁回答", "tags": ["风格"], "confidence": 0.9}
    ]"""
    result = parse_extraction_response(raw)
    assert len(result) == 1
    assert result[0].type == "preference"
    assert result[0].content == "用户偏好简洁回答"
    assert result[0].confidence == 0.9


def test_parse_markdown_fenced_json() -> None:
    raw = """```json
[{"type": "profile", "content": "用户是产品经理", "confidence": 0.85}]
```"""
    result = parse_extraction_response(raw)
    assert len(result) == 1
    assert result[0].type == "profile"


def test_skip_short_content() -> None:
    raw = '[{"type": "semantic", "content": "短", "confidence": 0.9}]'
    assert parse_extraction_response(raw) == []
