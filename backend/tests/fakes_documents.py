"""In-memory stand-in for DocumentService, mirroring its public interface."""

import itertools
from datetime import datetime, timedelta, timezone

from app.core.errors import ConflictError, NotFoundError


class InMemoryDocuments:
    def __init__(self):
        self._ids = itertools.count(1)
        self._clock = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.docs: dict[str, dict] = {}

    def _tick(self):
        self._clock += timedelta(seconds=1)
        return self._clock

    def _get(self, document_id):
        if document_id not in self.docs:
            raise NotFoundError("Document not found")
        return self.docs[document_id]

    async def create(self, fields):
        if any(d["content_hash"] == fields["content_hash"] for d in self.docs.values()):
            raise ConflictError("This file has already been uploaded.")
        doc_id = f"{next(self._ids):024x}"
        self.docs[doc_id] = {
            "id": doc_id,
            "processing_status": "pending",
            "progress": 0,
            "chunk_count": 0,
            "page_count": None,
            "char_count": 0,
            "text_preview": "",
            "error": None,
            "uploaded_at": self._tick(),
            "processed_at": None,
            **fields,
        }
        return dict(self.docs[doc_id])

    async def find_by_hash(self, content_hash):
        for d in self.docs.values():
            if d["content_hash"] == content_hash:
                return dict(d)
        return None

    async def get(self, document_id):
        return dict(self._get(document_id))

    async def list(self):
        return sorted((dict(d) for d in self.docs.values()), key=lambda d: d["uploaded_at"], reverse=True)

    async def update(self, document_id, **fields):
        if document_id not in self.docs:
            return False
        self.docs[document_id].update(fields)
        return True

    async def delete(self, document_id):
        self._get(document_id)
        return self.docs.pop(document_id)

    async def fail_unfinished(self, message):
        count = 0
        for d in self.docs.values():
            if d["processing_status"] in ("pending", "processing"):
                d.update(processing_status="failed", error=message, progress=0)
                count += 1
        return count
