"""Document processing pipeline: extract -> clean -> chunk -> (index in Phase 6)."""

import asyncio
import logging
from typing import Any, Protocol

from app.core.errors import AppError, BadRequestError, NotFoundError
from app.schemas.settings import RagSettings
from app.services.file_storage import FileStorage
from app.services.settings_service import SettingsService
from app.services.text_extraction import ExtractedDocument, Page, extract_text
from app.services.text_processing import Chunk, chunk_document, clean_text
from app.utils.clock import utcnow

logger = logging.getLogger(__name__)

PREVIEW_CHARS = 300


class Indexer(Protocol):
    """Implemented in Phase 6 (embeddings + ChromaDB). Until then the pipeline stops after chunking."""

    async def index(self, document: dict[str, Any], chunks: list[Chunk]) -> None: ...

    async def remove(self, document_id: str) -> None: ...


def build_chunks(
    extracted: ExtractedDocument, *, document: dict[str, Any], rag: RagSettings
) -> tuple[list[Chunk], int]:
    """Clean the extracted pages and split them into chunks. Returns (chunks, total character count)."""
    join_lines = document["file_type"] == "pdf"  # PDF lines wrap mid-sentence; other formats do not
    pages = [Page(p.number, clean_text(p.text, join_lines=join_lines)) for p in extracted.pages]
    chars = sum(len(p.text) for p in pages)
    chunks = chunk_document(
        pages,
        document_id=document["id"],
        document_name=document["filename"],
        uploaded_at=document["uploaded_at"].isoformat(),
        chunk_size=rag.chunk_size,
        chunk_overlap=rag.chunk_overlap,
    )
    return chunks, chars


class DocumentPipeline:
    def __init__(
        self,
        documents,
        storage: FileStorage,
        settings_service: SettingsService,
        indexer: Indexer | None = None,
        max_concurrent: int = 2,
    ):
        self.documents = documents
        self.storage = storage
        self.settings = settings_service
        self.indexer = indexer
        self._semaphore = asyncio.Semaphore(max(1, max_concurrent))

    # ------------------------------------------------------------- processing
    async def process(self, document_id: str) -> None:
        """Run in the background after upload. Never raises: failures are recorded on the document."""
        async with self._semaphore:
            try:
                await self._run(document_id)
            except Exception:
                logger.exception("Unexpected failure while processing document %s", document_id)

    async def _set(self, document_id: str, status: str, progress: int) -> bool:
        """Update progress. False means the document was deleted meanwhile, so processing should stop."""
        return await self.documents.update(document_id, processing_status=status, progress=progress)

    async def _run(self, document_id: str) -> None:
        try:
            document = await self.documents.get(document_id)
        except NotFoundError:
            return

        try:
            if not await self._set(document_id, "processing", 5):
                return
            path = self.storage.path_for(document["stored_name"])
            extracted = await asyncio.to_thread(extract_text, path, document["file_type"])

            if not await self._set(document_id, "processing", 40):
                return
            chunks, chars = await asyncio.to_thread(
                build_chunks, extracted, document=document, rag=self.settings.get().rag
            )
            if not chunks:
                raise BadRequestError(
                    "No readable text was found in this document. Scanned or image-only files are not supported."
                )

            if not await self._set(document_id, "processing", 70):
                return
            if self.indexer:
                await self.indexer.index(document, chunks)

            await self.documents.update(
                document_id,
                processing_status="completed",
                progress=100,
                chunk_count=len(chunks),
                page_count=extracted.page_count,
                char_count=chars,
                text_preview=chunks[0].text[:PREVIEW_CHARS],
                error=None,
                processed_at=utcnow(),
            )
            logger.info("Processed %s: %d chunks, %d characters", document["filename"], len(chunks), chars)
        except Exception as exc:
            if isinstance(exc, AppError):
                message = exc.detail
            else:
                logger.exception("Processing failed for %s", document["filename"])
                message = "Could not process this file. It may be corrupted or in an unsupported format."
            await self.documents.update(document_id, processing_status="failed", progress=0, error=message)

    # --------------------------------------------------------------- deletion
    async def remove(self, document_id: str) -> None:
        """Delete a document completely: vectors (Phase 6), the stored file, then the record."""
        document = await self.documents.get(document_id)
        if self.indexer:
            await self.indexer.remove(document_id)
        try:
            self.storage.delete(document["stored_name"])
        except OSError:
            logger.exception("Could not delete file for document %s", document_id)
            raise AppError("The file could not be deleted. Close any program using it and try again.") from None
        await self.documents.delete(document_id)
