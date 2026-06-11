"""审计日志展示测试."""

from app.desktop.context_panel import ContextPanel


def test_chat_completed_not_truncated() -> None:
    detail = {
        "conversation_id": "conv_abc",
        "project_id": None,
        "skills": [],
        "memories": ["mem_001", "mem_002"],
        "documents": ["report.pdf"],
        "has_reasoning": True,
    }
    text = ContextPanel._format_audit_detail("chat_completed", detail)
    assert "mem_001" in text
    assert "mem_002" in text
    assert "report.pdf" in text
    assert "memo" not in text or "memories" in text or "mem_001" in text


def test_fallback_json_not_truncated() -> None:
    detail = {"key": "x" * 200}
    text = ContextPanel._format_audit_detail("custom_event", detail)
    assert len(text) > 80
    assert "x" * 200 in text
