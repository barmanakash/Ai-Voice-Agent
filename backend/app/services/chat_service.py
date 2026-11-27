"""Orchestrates one persisted chat turn: prepare (validate + save user message), then stream."""

import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import anyio

from app.core.errors import AppError, describe_exception
from app.schemas.chat import ChatStreamRequest
from app.schemas.settings import RuntimeSettings
from app.services.ollama_service import OllamaService, build_chat_messages

logger = logging.getLogger(__name__)

TITLE_MAX_CHARS = 50


def make_title(text: str) -> str:
    """Conversation title from the first user message."""
    clean = " ".join(text.split())
    if len(clean) <= TITLE_MAX_CHARS:
        return clean or "New chat"
    return clean[:TITLE_MAX_CHARS].rstrip() + "…"


@dataclass
class TurnContext:
    conversation: dict[str, Any]
    user_message: dict[str, Any]
    history: list[dict[str, Any]]  # messages before the user message
    model: str
    num_ctx: int
    history_limit: int


class ChatService:
    def __init__(self, conversations, ollama: OllamaService, system_prompt: str):
        self.conversations = conversations
        self.ollama = ollama
        self.system_prompt = system_prompt

    async def prepare(self, req: ChatStreamRequest, settings: RuntimeSettings) -> TurnContext:
        """
        Everything that can fail with a proper HTTP status happens here, before streaming starts.
        Model availability is checked first so a failed request leaves nothing behind.
        """
        model = req.model or settings.model
        await self.ollama.ensure_model(model)

        if req.regenerate:
            if not req.conversation_id:
                raise AppError("There is no conversation to regenerate a response in.", status_code=400)
            conversation = await self.conversations.get_conversation(req.conversation_id)
            messages = await self.conversations.list_messages(conversation["id"])

            last_user = max((i for i, m in enumerate(messages) if m["role"] == "user"), default=None)
            if last_user is None:
                raise AppError("This conversation has no message to regenerate a response for.", status_code=400)

            # Drop the old answer(s); keep the user message that prompted them.
            await self.conversations.delete_messages([m["id"] for m in messages[last_user + 1 :]])
            user_message = messages[last_user]
            history = messages[:last_user]
        else:
            if req.conversation_id:
                conversation = await self.conversations.get_conversation(req.conversation_id)
                history = await self.conversations.list_messages(conversation["id"])
            else:
                conversation = await self.conversations.create_conversation(make_title(req.message), model)
                history = []
            user_message = await self.conversations.add_message(conversation["id"], "user", req.message)

        return TurnContext(
            conversation=conversation,
            user_message=user_message,
            history=history,
            model=model,
            num_ctx=settings.context_window,
            history_limit=settings.history_limit,
        )

    async def stream(self, ctx: TurnContext) -> AsyncIterator[dict[str, Any]]:
        """Yield events: meta, token*, then done or error. The answer is saved even if the client stops early."""
        yield {
            "type": "meta",
            "conversation_id": ctx.conversation["id"],
            "user_message_id": ctx.user_message["id"],
            "title": ctx.conversation["title"],
        }

        parts: list[str] = []
        error: str | None = None
        saved: dict[str, Any] | None = None

        try:
            messages = build_chat_messages(
                self.system_prompt,
                [{"role": m["role"], "content": m["content"]} for m in ctx.history],
                ctx.user_message["content"],
                ctx.history_limit,
            )
            async for chunk in self.ollama.chat_stream(messages, ctx.model, ctx.num_ctx):
                parts.append(chunk)
                yield {"type": "token", "content": chunk}
        except Exception as exc:  # CancelledError / GeneratorExit are not Exceptions and pass through
            error = describe_exception(exc)
        finally:
            content = "".join(parts)
            if content.strip():
                # Shielded so the save still completes when the client disconnects (Stop generation).
                with anyio.CancelScope(shield=True):
                    try:
                        saved = await self.conversations.add_message(
                            ctx.conversation["id"], "assistant", content, sources=[], model_name=ctx.model
                        )
                    except Exception:
                        logger.exception("Failed to save the assistant message")
                        error = error or "The response was generated but could not be saved to the database."

        if error:
            yield {"type": "error", "detail": error}
        elif saved is None:
            yield {"type": "error", "detail": "The model returned an empty response. Please try again."}
        else:
            yield {"type": "done", "message_id": saved["id"], "used_knowledge_base": False}
