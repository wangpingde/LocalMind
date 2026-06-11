"""记忆相似度去重测试."""

from app.core.memory.memory_manager import MemoryManager


class _FakeSqlite:
    def __init__(self, memories: list) -> None:
        self._memories = memories

    def list_memories(self, memory_type=None, keyword=None):
        return self._memories


class _Mem:
    def __init__(self, id: str, content: str, status: str = "active", confidence: float = 1.0):
        self.id = id
        self.content = content
        self.status = status
        self.confidence = confidence


def test_find_similar_by_substring() -> None:
    existing = "\u7528\u6237\u504f\u597d\u7ed3\u6784\u5316\u56de\u7b54"
    query = "\u7528\u6237\u504f\u597d\u7ed3\u6784\u5316"
    mgr = MemoryManager(_FakeSqlite([_Mem("m1", existing)]), None, None)  # type: ignore[arg-type]
    hit = mgr.find_similar(query)
    assert hit is not None
    assert hit.id == "m1"


def test_find_similar_by_bigram_overlap() -> None:
    existing = "\u7528\u6237\u504f\u597d\u7ed3\u6784\u5316\u56de\u7b54"
    query = "\u7528\u6237\u504f\u597d\u7ed3\u6784\u5316\u3001\u53ef\u843d\u5730\u7684\u56de\u7b54"
    mgr = MemoryManager(_FakeSqlite([_Mem("m1", existing)]), None, None)  # type: ignore[arg-type]
    hit = mgr.find_similar(query)
    assert hit is not None


def test_find_similar_no_match() -> None:
    existing = "\u5b8c\u5168\u4e0d\u540c\u7684\u5185\u5bb9"
    query = "\u7528\u6237\u559c\u6b22 Python \u7f16\u7a0b"
    mgr = MemoryManager(_FakeSqlite([_Mem("m1", existing)]), None, None)  # type: ignore[arg-type]
    assert mgr.find_similar(query) is None
