"""知识库上传与删除测试."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("LOCALMIND_DATA_DIR", str(Path(__file__).resolve().parent.parent / ".dev-data"))


@pytest.fixture
def client():
    from app.server.api import create_app
    from app.services import init_services
    from fastapi.testclient import TestClient

    init_services()
    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture
def svc():
    from app.services import init_services

    return init_services()


def test_upload_and_delete_document(client, svc, monkeypatch):
    filename = f"pytest_{uuid.uuid4().hex[:8]}.md"
    content = b"# Hello Knowledge\n\nTest upload."

    monkeypatch.setattr(
        svc.model_gateway,
        "embed",
        MagicMock(return_value=[[0.1, 0.2, 0.3]]),
    )

    resp = client.post(
        f"/api/knowledge/upload?subdir=inbox&reindex=true",
        files={"files": (filename, content, "text/markdown")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert len(data["saved"]) == 1
    rel_path = data["saved"][0]["path"]
    assert (svc.workspace.knowledge_dir / rel_path).exists()

    listed = client.get("/api/knowledge/documents")
    assert listed.status_code == 200
    docs = listed.json()["documents"]
    note = next(
        d for d in docs
        if d["filename"] == filename or d["path"].replace("\\", "/") == rel_path
    )
    doc_id = note["id"]

    deleted = client.delete(f"/api/knowledge/documents/{doc_id}")
    assert deleted.status_code == 200
    assert not (svc.workspace.knowledge_dir / rel_path).exists()
    assert svc.sqlite.get_document(doc_id) is None


def test_upload_to_project_subdir(client, svc, monkeypatch):
    monkeypatch.setattr(
        svc.model_gateway,
        "embed",
        MagicMock(return_value=[[0.1, 0.2, 0.3]]),
    )
    project = svc.projects.create_project(f"PyTestProj_{uuid.uuid4().hex[:6]}", "demo")
    subdir = f"projects/{project.slug}"
    filename = f"pytest_{uuid.uuid4().hex[:8]}.md"

    resp = client.post(
        f"/api/knowledge/upload?subdir={subdir}&reindex=true",
        files={"files": (filename, b"# project doc", "text/markdown")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    rel_path = data["saved"][0]["path"]
    assert rel_path.startswith(f"projects/{project.slug}/")
    assert (svc.workspace.knowledge_dir / rel_path).exists()

    svc.indexer.delete_document_file(
        next(
            d.id
            for d in svc.sqlite.list_documents()
            if d.path.replace("\\", "/") == rel_path
        )
    )


def test_upload_unsupported_format(client):
    resp = client.post(
        "/api/knowledge/upload",
        files={"files": ("image.bin", b"\x00\x01", "application/octet-stream")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "error"
    assert data["errors"]
