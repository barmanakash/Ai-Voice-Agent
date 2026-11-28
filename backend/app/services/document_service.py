"""MongoDB access for document metadata. Files live on disk; only metadata lives here."""

from typing import Any

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import DuplicateKeyError

from app.core.errors import ConflictError, NotFoundError
from app.utils.clock import utcnow

LIST_LIMIT = 500


def to_object_id(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except (InvalidId, TypeError):
        raise NotFoundError("Document not found") from None


def document_to_dict(doc: dict[str, Any]) -> dict[str, Any]:
    out = {k: v for k, v in doc.items() if k != "_id"}
    out["id"] = str(doc["_id"])
    return out


class DocumentService:
    def __init__(self, db):
        self._collection = db["documents"]

    async def create(self, fields: dict[str, Any]) -> dict[str, Any]:
        doc = {
            "processing_status": "pending",
            "progress": 0,
            "chunk_count": 0,
            "page_count": None,
            "char_count": 0,
            "text_preview": "",
            "error": None,
            "uploaded_at": utcnow(),
            "processed_at": None,
            **fields,
        }
        try:
            result = await self._collection.insert_one(doc)
        except DuplicateKeyError:
            raise ConflictError("This file has already been uploaded.") from None
        doc["_id"] = result.inserted_id
        return document_to_dict(doc)

    async def find_by_hash(self, content_hash: str) -> dict[str, Any] | None:
        doc = await self._collection.find_one({"content_hash": content_hash})
        return document_to_dict(doc) if doc else None

    async def get(self, document_id: str) -> dict[str, Any]:
        doc = await self._collection.find_one({"_id": to_object_id(document_id)})
        if doc is None:
            raise NotFoundError("Document not found")
        return document_to_dict(doc)

    async def list(self) -> list[dict[str, Any]]:
        cursor = self._collection.find().sort("uploaded_at", -1).limit(LIST_LIMIT)
        return [document_to_dict(d) for d in await cursor.to_list(length=LIST_LIMIT)]

    async def update(self, document_id: str, **fields: Any) -> bool:
        """Returns False if the document no longer exists (e.g. it was deleted while being processed)."""
        result = await self._collection.update_one({"_id": to_object_id(document_id)}, {"$set": fields})
        return result.matched_count > 0

    async def delete(self, document_id: str) -> dict[str, Any]:
        doc = await self._collection.find_one_and_delete({"_id": to_object_id(document_id)})
        if doc is None:
            raise NotFoundError("Document not found")
        return document_to_dict(doc)

    async def fail_unfinished(self, message: str) -> int:
        """Mark documents left pending/processing by a crash or restart as failed."""
        result = await self._collection.update_many(
            {"processing_status": {"$in": ["pending", "processing"]}},
            {"$set": {"processing_status": "failed", "error": message, "progress": 0}},
        )
        return result.modified_count
