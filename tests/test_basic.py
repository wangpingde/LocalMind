"""基础冒烟测试."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("LOCALMIND_DATA_DIR", str(Path(__file__).resolve().parent.parent / ".dev-data"))


@pytest.fixture
def client():
    from app.server.api import create_app
    from app.services import init_services

    init_services()
    with TestClient(create_app()) as test_client:
        yield test_client


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_skills_loaded(client):
    resp = client.get("/api/skills")
    assert resp.status_code == 200
    skills = resp.json()
    assert len(skills) >= 3
    ids = {s["id"] for s in skills}
    assert "product_architect" in ids


def test_memory_crud(client):
    resp = client.post(
        "/api/memories",
        json={"type": "preference", "content": "偏好结构化回答", "tags": ["风格"]},
    )
    assert resp.status_code == 200
    mem_id = resp.json()["id"]

    resp2 = client.get("/api/memories")
    assert any(m["id"] == mem_id for m in resp2.json())

    client.delete(f"/api/memories/{mem_id}")


def test_skill_selector_keyword():
    from app.services import init_services

    svc = init_services()
    settings = svc.config.load_settings()
    selected = svc.skill_selector.select("帮我写一份 PRD", settings)
    assert any(s.id == "product_architect" for s in selected)
