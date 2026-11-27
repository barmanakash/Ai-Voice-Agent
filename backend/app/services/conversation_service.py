"""MongoDB access for conversations and messages. IDs cross this boundary as strings."""

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo import ReturnDocument

from app.core.errors import NotFoundError

LIST_LIMIT = 200


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_object_id(value: str, what: str = "Conversation") -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise NotFoundError(f"{what} not found") from None


def conversation_to_dict(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "title": doc["title"],
        "created_at": doc["created_at"],
        "updated_at": doc["updated_at"],
        "model_name": doc.get("model_name"),
    }


def message_to_dict(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "conversation_id": str(doc["conversation_id"]),
        "role": doc["role"],
        "content": doc["content"],
        "created_at": doc["created_at"],
        "sources": doc.get("sources", []),
    }


class ConversationService:
    def __init__(self, db):
        self._conversations = db["conversations"]
        self._messages = db["messages"]

    # ------------------------------------------------------------ conversations
    async def list_conversations(self) -> list[dict[str, Any]]:
        cursor = self._conversations.find().sort("updated_at", -1).limit(LIST_LIMIT)
        return [conversation_to_dict(d) for d in await cursor.to_list(length=LIST_LIMIT)]

    async def create_conversation(self, title: str, model_name: str | None = None) -> dict[str, Any]:
        now = utcnow()
        doc = {"title": title, "created_at": now, "updated_at": now, "model_name": model_name}
        result = await self._conversations.insert_one(doc)
        doc["_id"] = result.inserted_id
        return conversation_to_dict(doc)

    async def get_conversation(self, conversation_id: str) -> dict[str, Any]:
        doc = await self._conversations.find_one({"_id": to_object_id(conversation_id)})
        if doc is None:
            raise NotFoundError("Conversation not found")
        return conversation_to_dict(doc)

    async def rename_conversation(self, conversation_id: str, title: str) -> dict[str, Any]:
        doc = await self._conversations.find_one_and_update(
            {"_id": to_object_id(conversation_id)},
            {"$set": {"title": title}},
            return_document=ReturnDocument.AFTER,
        )
        if doc is None:
            raise NotFoundError("Conversation not found")
        return conversation_to_dict(doc)

    async def delete_conversation(self, conversation_id: str) -> None:
        oid = to_object_id(conversation_id)
        result = await self._conversations.delete_one({"_id": oid})
        if result.deleted_count == 0:
            raise NotFoundError("Conversation not found")
        await self._messages.delete_many({"conversation_id": oid})

    async def clear_messages(self, conversation_id: str) -> None:
        oid = to_object_id(conversation_id)
        result = await self._conversations.update_one({"_id": oid}, {"$set": {"updated_at": utcnow()}})
        if result.matched_count == 0:
            raise NotFoundError("Conversation not found")
        await self._messages.delete_many({"conversation_id": oid})

    # ----------------------------------------------------------------- messages
    async def list_messages(self, conversation_id: str) -> list[dict[str, Any]]:
        cursor = self._messages.find({"conversation_id": to_object_id(conversation_id)}).sort(
            [("created_at", 1), ("_id", 1)]
        )
        return [message_to_dict(d) for d in await cursor.to_list(length=None)]

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        sources: list[dict[str, Any]] | None = None,
        model_name: str | None = None,
    ) -> dict[str, Any]:
        """Insert a message and bump the conversation's updated_at (and model_name if given)."""
        oid = to_object_id(conversation_id)
        now = utcnow()
        doc = {
            "conversation_id": oid,
            "role": role,
            "content": content,
            "created_at": now,
            "sources": sources or [],
        }
        result = await self._messages.insert_one(doc)
        doc["_id"] = result.inserted_id

        update: dict[str, Any] = {"updated_at": now}
        if model_name:
            update["model_name"] = model_name
        await self._conversations.update_one({"_id": oid}, {"$set": update})
        return message_to_dict(doc)

    async def delete_messages(self, message_ids: list[str]) -> None:
        if message_ids:
            await self._messages.delete_many({"_id": {"$in": [to_object_id(i, "Message") for i in message_ids]}})
