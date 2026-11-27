import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.config import Config
from app.core.dependencies import (
    get_app_config,
    get_chat_service,
    get_ollama,
    get_settings_service,
)
from app.schemas.chat import ChatReply, ChatRequest, ChatResponse, ChatStreamRequest
from app.services.chat_service import ChatService
from app.services.ollama_service import OllamaService, build_chat_messages
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/chat", tags=["chat"])


async def _ndjson(events: AsyncIterator[dict[str, Any]]) -> AsyncIterator[str]:
    """Encode events as newline-delimited JSON, one object per line."""
    async for event in events:
        yield json.dumps(event, ensure_ascii=False) + "\n"


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    config: Config = Depends(get_app_config),
    ollama: OllamaService = Depends(get_ollama),
    settings_service: SettingsService = Depends(get_settings_service),
):
    """Stateless, non-streaming chat: the caller supplies the history and nothing is saved."""
    settings = settings_service.get()
    model = body.model or settings.model

    messages = build_chat_messages(
        system_prompt=config.system_prompt,
        history=[m.model_dump() for m in body.history],
        user_message=body.message,
        history_limit=settings.history_limit,
    )
    answer = await ollama.chat(messages, model=model, num_ctx=settings.context_window)
    return ChatResponse(message=ChatReply(content=answer), model=model)


@router.post("/stream")
async def chat_stream(
    body: ChatStreamRequest,
    chat_service: ChatService = Depends(get_chat_service),
    settings_service: SettingsService = Depends(get_settings_service),
):
    """
    Persistent streaming chat (newline-delimited JSON).

    Events: meta -> token* -> done, or error. Problems found before streaming starts
    (unknown conversation, model missing, Ollama offline) return a normal HTTP error instead.
    """
    ctx = await chat_service.prepare(body, settings_service.get())
    return StreamingResponse(
        _ndjson(chat_service.stream(ctx)),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
