"""Extract raw text from uploaded documents. These functions are synchronous; call them in a thread."""

import zipfile
from dataclasses import dataclass
from pathlib import Path

import docx
from docx.opc.exceptions import PackageNotFoundError
from docx.table import Table
from docx.text.paragraph import Paragraph

try:
    import pymupdf
except ImportError:  # older PyMuPDF releases only expose "fitz"
    import fitz as pymupdf

from app.core.errors import BadRequestError, UnsupportedFileTypeError

MAX_DOCX_UNPACKED_BYTES = 300 * 1024 * 1024


@dataclass
class Page:
    number: int | None  # 1-based page number, or None when the format has no pages
    text: str


@dataclass
class ExtractedDocument:
    pages: list[Page]
    page_count: int | None


def _extract_pdf(path: Path) -> ExtractedDocument:
    try:
        doc = pymupdf.open(str(path))
    except Exception:
        raise BadRequestError("This PDF could not be opened. The file may be corrupted.") from None

    try:
        if doc.needs_pass:
            raise BadRequestError("This PDF is password-protected. Remove the password and upload it again.")
        pages: list[Page] = []
        for number, page in enumerate(doc, start=1):
            # "blocks" keeps paragraph structure: lines inside a block are joined later, blocks stay separate.
            blocks = page.get_text("blocks", sort=True)
            text = "\n\n".join(b[4].strip() for b in blocks if len(b) > 6 and b[6] == 0 and b[4].strip())
            pages.append(Page(number, text))
        return ExtractedDocument(pages, len(pages))
    finally:
        doc.close()


def _extract_docx(path: Path) -> ExtractedDocument:
    try:
        with zipfile.ZipFile(path) as archive:
            if sum(i.file_size for i in archive.infolist()) > MAX_DOCX_UNPACKED_BYTES:
                raise BadRequestError("This .docx file is too large once unpacked.")
        document = docx.Document(str(path))
    except (zipfile.BadZipFile, PackageNotFoundError, KeyError):
        raise BadRequestError("This file is not a valid .docx document.") from None

    parts: list[str] = []
    # Walk the body in order so tables stay where they appear in the document.
    for child in document.element.body.iterchildren():
        if child.tag.endswith("}p"):
            text = Paragraph(child, document).text.strip()
            if text:
                parts.append(text)
        elif child.tag.endswith("}tbl"):
            for row in Table(child, document).rows:
                cells: list[str] = []
                for cell in row.cells:
                    value = cell.text.strip()
                    if value and (not cells or cells[-1] != value):  # merged cells repeat their text
                        cells.append(value)
                if cells:
                    parts.append(" | ".join(cells))
    return ExtractedDocument([Page(None, "\n\n".join(parts))], None)


def decode_text(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")  # common for older Windows text files


def _extract_plain(path: Path) -> ExtractedDocument:
    return ExtractedDocument([Page(None, decode_text(path.read_bytes()))], None)


def extract_text(path: Path, file_type: str) -> ExtractedDocument:
    if file_type == "pdf":
        return _extract_pdf(path)
    if file_type == "docx":
        return _extract_docx(path)
    if file_type in ("txt", "md"):
        return _extract_plain(path)
    raise UnsupportedFileTypeError(f"Unsupported file type: {file_type}")
