from datetime import datetime
from typing import Literal

from pydantic import BaseModel

ProcessingStatus = Literal["pending", "processing", "completed", "failed"]


class DocumentOut(BaseModel):
    """Public view of a document. Internal fields (stored file name, content hash) are never exposed."""

    id: str
    filename: str
    file_type: str
    file_size: int
    processing_status: ProcessingStatus
    progress: int = 0
    chunk_count: int = 0
    page_count: int | None = None
    char_count: int = 0
    text_preview: str = ""
    error: str | None = None
    uploaded_at: datetime
    processed_at: datetime | None = None


class DocumentStatus(BaseModel):
    id: str
    processing_status: ProcessingStatus
    progress: int = 0
    chunk_count: int = 0
    error: str | None = None
