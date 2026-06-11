"""索引清理测试."""

from pathlib import Path

from app.core.rag.indexer import DocumentIndexer


class _FakeDoc:
    def __init__(self, doc_id: str, path: str, filename: str, status: str = "indexed"):
        self.id = doc_id
        self.path = path
        self.filename = filename
        self.status = status


class _FakeSqlite:
    def __init__(self, docs: list[_FakeDoc]) -> None:
        self.docs = {d.id: d for d in docs}
        self.deleted: list[str] = []

    def list_documents(self):
        return list(self.docs.values())

    def get_document_by_path(self, path: str):
        for d in self.docs.values():
            if d.path == path:
                return d
        return None

    def delete_document(self, document_id: str) -> bool:
        if document_id in self.docs:
            del self.docs[document_id]
            self.deleted.append(document_id)
            return True
        return False


class _FakeVector:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    def delete_document_vectors(self, document_id: str) -> None:
        self.deleted.append(document_id)


class _FakeWorkspace:
    def __init__(self, knowledge_dir: Path) -> None:
        self.knowledge_dir = knowledge_dir


class _FakeAudit:
    def log(self, *args, **kwargs) -> None:
        pass


def test_prune_stale_index(tmp_path: Path) -> None:
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    sqlite = _FakeSqlite(
        [
            _FakeDoc("doc1", "inbox/gone.pdf", "gone.pdf"),
            _FakeDoc("doc2", "inbox/exists.txt", "exists.txt"),
        ]
    )
    (knowledge / "inbox").mkdir()
    (knowledge / "inbox" / "exists.txt").write_text("hello", encoding="utf-8")

    indexer = DocumentIndexer(
        _FakeWorkspace(knowledge),  # type: ignore[arg-type]
        sqlite,  # type: ignore[arg-type]
        _FakeVector(),  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        _FakeAudit(),  # type: ignore[arg-type]
    )

    removed = indexer.prune_stale_index()
    assert removed == 1
    assert "doc1" in sqlite.deleted
    assert "doc2" in sqlite.docs
