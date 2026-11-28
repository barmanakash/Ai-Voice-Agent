import logging

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)


class MongoManager:
    """Owns the MongoDB client. Datetimes are timezone-aware (UTC) so the API emits proper ISO strings."""

    def __init__(self, uri: str, db_name: str, timeout_ms: int = 3000):
        self._client = AsyncMongoClient(uri, tz_aware=True, serverSelectionTimeoutMS=timeout_ms)
        self.db = self._client[db_name]

    async def ping(self) -> bool:
        try:
            await self._client.admin.command("ping")
            return True
        except PyMongoError:
            return False

    async def ensure_indexes(self) -> None:
        # Conversation list is sorted by most recently updated.
        await self.db["conversations"].create_index([("updated_at", DESCENDING)])
        # Messages are always read per conversation in chronological order.
        await self.db["messages"].create_index([("conversation_id", ASCENDING), ("created_at", ASCENDING)])
        # Documents: newest first, and one record per unique file content (duplicate prevention).
        await self.db["documents"].create_index([("uploaded_at", DESCENDING)])
        await self.db["documents"].create_index("content_hash", unique=True)

    async def close(self) -> None:
        try:
            await self._client.close()
        except Exception:  # pragma: no cover - best effort on shutdown
            pass
