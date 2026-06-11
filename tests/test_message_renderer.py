"""消息渲染测试."""

from app.desktop.message_renderer import _has_markdown, _looks_like_json, render_message_body


def test_json_render() -> None:
    html_out = render_message_body('{"name": "test", "ok": true}')
    assert "<pre" in html_out
    assert "test" in html_out
    assert "&quot;" not in html_out


def test_markdown_code_block() -> None:
    text = "说明：\n\n```python\nprint('hi')\n```"
    html_out = render_message_body(text, role="assistant")
    assert "print" in html_out
    assert "<pre" in html_out


def test_markdown_heading() -> None:
    text = "## 标题\n\n正文"
    assert _has_markdown(text)
    html_out = render_message_body(text, role="assistant")
    assert "<h2" in html_out


def test_plain_text() -> None:
    html_out = render_message_body("普通一句话", role="assistant")
    assert "普通一句话" in html_out


def test_looks_like_json() -> None:
    assert _looks_like_json('[1, 2, 3]')
    assert not _looks_like_json("not json")


def test_streaming_unclosed_fence() -> None:
    text = "说明\n\n```python\nprint('hi')"
    html_out = render_message_body(text, role="assistant", streaming=True)
    assert "print" in html_out
    assert "<h2" not in html_out
