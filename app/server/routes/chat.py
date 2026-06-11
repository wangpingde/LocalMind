"""聊天路由."""

from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services import get_services

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str
    project_id: str | None = None
    model: str | None = None
    stream: bool = False


@router.post("/chat")
def chat(req: ChatRequest):
    svc = get_services()
    if req.stream:
        gen = svc.agent.run(
            req.message,
            conversation_id=req.conversation_id,
            model=req.model,
            stream=True,
            project_id=req.project_id,
        )

        def event_stream():
            for event in gen:
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    result = svc.agent.run(
        req.message,
        conversation_id=req.conversation_id,
        model=req.model,
        stream=False,
        project_id=req.project_id,
    )
    return svc.agent.response_to_dict(result)  # type: ignore[arg-type]


@router.get("/conversations")
def list_conversations():
    svc = get_services()
    return [
        {"id": c.id, "title": c.title, "created_at": c.created_at, "updated_at": c.updated_at}
        for c in svc.sqlite.list_conversations()
    ]


@router.get("/conversations/{conv_id}/messages")
def get_messages(conv_id: str):
    svc = get_services()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at,
            "model_name": m.model_name,
        }
        for m in svc.sqlite.get_messages(conv_id)
    ]
