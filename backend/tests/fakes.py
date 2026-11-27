"""In-memory fakes so tests need neither Ollama nor MongoDB."""

import itertools
from datetime import datetime, timedelta, timezone

from app.core.errors import ModelNotAvailableError, NotFoundError, OllamaUnavailableError
from app.services.ollama_service import model_is_installed


class FakeMongo:
    def __init__(self, online=True):
        self.online = online

    async def ping(self):
        return self.online


class FakeOllama:
    def __init__(self, installed=("qwen2.5:3b",), online=True, chunks=("Hello", " from", " Aria"), fail_after=None):
        self.installed = list(installed)
        self.online = online
        self.chunks = list(chunks)
        self.fail_after = fail_after  # raise OllamaUnavailableError after N chunks
        self.last_messages = None

    async def list_models(self):
        if not self.online:
            raise OllamaUnavailableError("Cannot connect to Ollama")
        return [{"name": n, "size": 1000, "modified_at": None} for n in self.installed]

    async def status(self, model):
        try:
            names = [m["name"] for m in await self.list_models()]
        except OllamaUnavailableError as exc:
            return {"ollama_connected": False, "model": model, "model_available": False, "message": exc.detail}
        ok = model_is_installed(model, names)
        return {"ollama_connected": True, "model": model, "model_available": ok,
                "message": "" if ok else f"missing {model}"}

    async def ensure_model(self, model):
        names = [m["name"] for m in await self.list_models()]
        if not model_is_installed(model, names):
            raise ModelNotAvailableError(f"Model {model} is not installed")

    async def chat(self, messages, model, num_ctx):
        await self.ensure_model(model)
        self.last_messages = messages
        return "Hello from the fake model"

    async def chat_stream(self, messages, model, num_ctx):
        await self.ensure_model(model)
        self.last_messages = messages
        for i, chunk in enumerate(self.chunks):
            if self.fail_after is not None and i >= self.fail_after:
                raise OllamaUnavailableError("Ollama went away")
            yield chunk


class InMemoryConversations:
    """Mirrors ConversationService's public interface."""

    def __init__(self):
        self._ids = itertools.count(1)
        self._clock = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.conversations: dict[str, dict] = {}
        self.messages: dict[str, dict] = {}

    def _now(self):
        self._clock += timedelta(seconds=1)
        return self._clock

    def _new_id(self):
        return f"{next(self._ids):024x}"  # looks like an ObjectId

    def _conv(self, cid):
        if cid not in self.conversations:
            raise NotFoundError("Conversation not found")
        return self.conversations[cid]

    async def list_conversations(self):
        return sorted(self.conversations.values(), key=lambda c: c["updated_at"], reverse=True)

    async def create_conversation(self, title, model_name=None):
        now, cid = self._now(), self._new_id()
        self.conversations[cid] = {"id": cid, "title": title, "created_at": now, "updated_at": now,
                                   "model_name": model_name}
        return dict(self.conversations[cid])

    async def get_conversation(self, cid):
        return dict(self._conv(cid))

    async def rename_conversation(self, cid, title):
        self._conv(cid)["title"] = title
        return dict(self.conversations[cid])

    async def delete_conversation(self, cid):
        self._conv(cid)
        del self.conversations[cid]
        self.messages = {k: v for k, v in self.messages.items() if v["conversation_id"] != cid}

    async def clear_messages(self, cid):
        self._conv(cid)["updated_at"] = self._now()
        self.messages = {k: v for k, v in self.messages.items() if v["conversation_id"] != cid}

    async def list_messages(self, cid):
        self._conv(cid)
        return [dict(m) for m in self.messages.values() if m["conversation_id"] == cid]

    async def add_message(self, cid, role, content, sources=None, model_name=None):
        conv = self._conv(cid)
        now, mid = self._now(), self._new_id()
        self.messages[mid] = {"id": mid, "conversation_id": cid, "role": role, "content": content,
                              "created_at": now, "sources": sources or []}
        conv["updated_at"] = now
        if model_name:
            conv["model_name"] = model_name
        return dict(self.messages[mid])

    async def delete_messages(self, ids):
        for i in ids:
            self.messages.pop(i, None)
