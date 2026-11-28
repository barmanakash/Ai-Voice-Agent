"""Secure handling of uploaded files. User input never decides where a file is written."""

import asyncio
import hashlib
import logging
import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.core.errors import BadRequestError, FileTooLargeError

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
READ_CHUNK = 1024 * 1024  # 1 MB


def sanitize_filename(name: str | None) -> str:
    """Keep only the base name, drop control characters, cap the length."""
    name = (name or "").replace("\\", "/").split("/")[-1]
    name = "".join(ch for ch in name if ch.isprintable()).strip()
    return name[:255]


def get_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


def check_signature(ext: str, head: bytes) -> None:
    """Make sure the content matches the extension, so a renamed .exe is not accepted as a .pdf."""
    if ext == ".pdf" and b"%PDF-" not in head[:1024]:
        raise BadRequestError("This file does not look like a valid PDF.")
    if ext == ".docx" and not head.startswith(b"PK\x03\x04"):
        raise BadRequestError("This file does not look like a valid .docx document.")
    if ext in (".txt", ".md") and b"\x00" in head:
        raise BadRequestError("This file looks like a binary file, not plain text.")


@dataclass
class SavedUpload:
    tmp_path: Path
    size: int
    sha256: str


class FileStorage:
    def __init__(self, uploads_dir: Path):
        self.dir = Path(uploads_dir).resolve()
        self.dir.mkdir(parents=True, exist_ok=True)

    async def save_upload(self, upload: UploadFile, ext: str, max_bytes: int) -> SavedUpload:
        """Stream the upload to a temporary file while enforcing the size limit and hashing the content."""
        tmp = self.dir / f".incoming-{uuid.uuid4().hex}.tmp"
        digest = hashlib.sha256()
        size = 0
        first = True
        try:
            with open(tmp, "wb") as f:
                while True:
                    chunk = await upload.read(READ_CHUNK)
                    if not chunk:
                        break
                    if first:
                        check_signature(ext, chunk[:4096])
                        first = False
                    size += len(chunk)
                    if size > max_bytes:
                        raise FileTooLargeError(f"The file is larger than the {max_bytes // (1024 * 1024)} MB limit.")
                    digest.update(chunk)
                    await asyncio.to_thread(f.write, chunk)
            if size == 0:
                raise BadRequestError("The file is empty.")
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        return SavedUpload(tmp_path=tmp, size=size, sha256=digest.hexdigest())

    def finalize(self, saved: SavedUpload, ext: str) -> str:
        """Move the temp file to its final, server-generated name and return that name."""
        stored_name = f"{uuid.uuid4().hex}{ext}"
        os.replace(saved.tmp_path, self.dir / stored_name)
        return stored_name

    def discard(self, saved: SavedUpload) -> None:
        saved.tmp_path.unlink(missing_ok=True)

    def path_for(self, stored_name: str) -> Path:
        """Resolve a stored file name, refusing anything that would escape the uploads directory."""
        path = (self.dir / stored_name).resolve()
        if path.parent != self.dir:
            raise ValueError("Invalid stored file name")
        return path

    def delete(self, stored_name: str) -> None:
        self.path_for(stored_name).unlink(missing_ok=True)
