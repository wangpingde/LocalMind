"""桌面端 HTTP 客户端."""

from __future__ import annotations

import json
from typing import Any, Generator

import httpx


class ApiClient:
    def __init__(self, base_url: str = "http://127.0.0.1:17777") -> None:
        self.base_url = base_url.rstrip("/")

    def _url(self, path: str) -> str:
        return f"{self.base_url}/api{path}"

    @staticmethod
    def _client(timeout: float) -> httpx.Client:
        # trust_env=False：访问本地 API 时绕过系统代理，
        # 防止代理软件劫持 127.0.0.1 导致请求超时 / 连接失败
        return httpx.Client(timeout=timeout, trust_env=False)

    def get(self, path: str) -> Any:
        with self._client(30.0) as client:
            resp = client.get(self._url(path))
            resp.raise_for_status()
            return resp.json()

    def post(self, path: str, data: dict | None = None) -> Any:
        with self._client(120.0) as client:
            resp = client.post(self._url(path), json=data or {})
            resp.raise_for_status()
            return resp.json()

    def put(self, path: str, data: dict) -> Any:
        with self._client(30.0) as client:
            resp = client.put(self._url(path), json=data)
            resp.raise_for_status()
            return resp.json()

    def delete(self, path: str) -> Any:
        with self._client(30.0) as client:
            resp = client.delete(self._url(path))
            resp.raise_for_status()
            return resp.json()

    def chat_stream(
        self,
        message: str,
        conversation_id: str | None = None,
        model: str | None = None,
        project_id: str | None = None,
    ) -> Generator[tuple[str, str, dict | None], None, None]:
        """yield (event_type, content, done_payload).
        event_type: chunk|reasoning|step|step_delta|answer_reset|done"""
        payload = {
            "message": message,
            "conversation_id": conversation_id,
            "model": model,
            "project_id": project_id,
            "stream": True,
        }
        with self._client(120.0) as client:
            with client.stream("POST", self._url("/chat"), json=payload) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        event_type = data.get("type", "")
                        if event_type == "chunk":
                            yield "chunk", data.get("content", ""), None
                        elif event_type == "reasoning":
                            yield "reasoning", data.get("content", ""), None
                        elif event_type == "step":
                            yield "step", json.dumps(data, ensure_ascii=False), None
                        elif event_type == "step_delta":
                            yield "step_delta", json.dumps(data, ensure_ascii=False), None
                        elif event_type == "answer_reset":
                            yield "answer_reset", "", None
                        elif event_type == "done":
                            yield "done", "", data

    def upload(
        self,
        path: str,
        file_path: str,
        *,
        params: dict | None = None,
        field_name: str = "file",
    ) -> Any:
        return self.upload_many(path, [file_path], params=params, field_name=field_name)

    def upload_many(
        self,
        path: str,
        file_paths: list[str],
        *,
        params: dict | None = None,
        field_name: str = "files",
    ) -> Any:
        with self._client(120.0) as client:
            file_handles = []
            multipart: list[tuple[str, tuple[str, object]]] = []
            try:
                for file_path in file_paths:
                    name = file_path.replace("\\", "/").rsplit("/", 1)[-1]
                    fh = open(file_path, "rb")
                    file_handles.append(fh)
                    multipart.append((field_name, (name, fh)))
                resp = client.post(self._url(path), files=multipart, params=params or {})
                resp.raise_for_status()
                return resp.json()
            finally:
                for fh in file_handles:
                    fh.close()
