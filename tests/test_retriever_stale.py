"""检索与清空索引一致性测试."""

from app.core.rag.retriever import RAGEngine


class _FakeDoc:
    def __init__(self, doc_id: str, path: str, filename: str, status: str = "indexed") -> None:
        self.id = doc_id
        self.path = path
        self.filename = filename
        self.status = status


class _FakeSqlite:
    def __init__(self, docs: list[_FakeDoc]) -> None:
        self._docs = docs

    def list_documents(self):
        return list(self._docs)

    def session(self):
        raise NotImplementedError


class _FakeVector:
    def search_documents(self, query_vector, top_k: int = 8):
        return [
            {
                "chunk_id": "chunk_stale",
                "document_id": "doc_gone",
                "path": "inbox/gone.pdf",
                "filename": "gone.pdf",
                "content": "旧文档内容",
                "summary": "旧文档",
                "page_no": 0,
                "heading_path": "",
            }
        ]


class _FakeGateway:
    def embed(self, texts):
        return [[0.1] * 384 for _ in texts]


def test_retrieve_ignores_orphan_vectors() -> None:
    rag = RAGEngine(_FakeVector(), _FakeSqlite([]), _FakeGateway())  # type: ignore[arg-type]
    resp = rag.retrieve("旧文档")
    assert resp.results == []
