"""Text cleaning and chunking. Pure functions with no I/O."""

import re
import unicodedata
from bisect import bisect_right
from dataclasses import dataclass

from app.services.text_extraction import Page

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WHITESPACE = re.compile(r"\s")
_BREAKS = ("\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ")  # best break first


def clean_text(text: str, join_lines: bool = False) -> str:
    """
    Normalize extracted text.

    join_lines=True is for PDFs, where lines wrap in the middle of sentences: single newlines become
    spaces and words split by a hyphen at a line end are re-joined. Blank lines (paragraphs) are kept.
    """
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ").replace("\u00ad", "")
    text = _CONTROL_CHARS.sub("", text)
    if join_lines:
        text = re.sub(r"(\w)-\n([a-z])", r"\1\2", text)
        text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _snap_end(text: str, start: int, end: int, size: int) -> int:
    """Move a chunk end back to a natural boundary (paragraph, line, sentence, word) in its last 40%."""
    low = start + int(size * 0.6)
    segment = text[low:end]
    for sep in _BREAKS:
        i = segment.rfind(sep)
        if i != -1:
            return low + i + len(sep)
    return end


def _snap_start(text: str, pos: int, end: int) -> int:
    """Don't start the next chunk in the middle of a word."""
    if pos > 0 and not text[pos - 1].isspace():
        match = _WHITESPACE.search(text, pos, end)
        if match:
            return match.end()
    return pos


def split_spans(text: str, size: int, overlap: int) -> list[tuple[int, int]]:
    """Return (start, end) character spans: at most `size` long, consecutive spans share ~`overlap` characters."""
    spans: list[tuple[int, int]] = []
    n = len(text)
    start = 0
    while start < n:
        end = min(start + size, n)
        if end < n:
            end = _snap_end(text, start, end, size)

        s, e = start, end
        while s < e and text[s].isspace():
            s += 1
        while e > s and text[e - 1].isspace():
            e -= 1
        if e > s:
            spans.append((s, e))

        if end >= n:
            break
        nxt = end - overlap
        if nxt <= start:  # overlap as large as the chunk: skip it so we always move forward
            nxt = end
        start = _snap_start(text, nxt, end)
    return spans


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    document_name: str
    index: int
    text: str
    page: int | None
    uploaded_at: str
    source: str

    def metadata(self) -> dict:
        """Metadata stored next to the vector in Phase 6 (ChromaDB values must be simple types)."""
        return {
            "document_id": self.document_id,
            "document_name": self.document_name,
            "chunk_id": self.chunk_id,
            "chunk_index": self.index,
            "page": self.page if self.page is not None else -1,
            "uploaded_at": self.uploaded_at,
            "source": self.source,
        }


def chunk_document(
    pages: list[Page],
    *,
    document_id: str,
    document_name: str,
    uploaded_at: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[Chunk]:
    """Chunk already-cleaned pages. Each chunk records the page where it starts."""
    texts: list[str] = []
    page_numbers: list[int | None] = []
    offsets: list[int] = []
    cursor = 0
    for page in pages:
        if not page.text:
            continue
        offsets.append(cursor)
        texts.append(page.text)
        page_numbers.append(page.number)
        cursor += len(page.text) + 2  # the "\n\n" joiner below

    corpus = "\n\n".join(texts)
    chunks: list[Chunk] = []
    for index, (start, end) in enumerate(split_spans(corpus, chunk_size, chunk_overlap)):
        page = page_numbers[bisect_right(offsets, start) - 1]
        source = f"{document_name}, page {page}" if page is not None else document_name
        chunks.append(
            Chunk(
                chunk_id=f"{document_id}-{index}",
                document_id=document_id,
                document_name=document_name,
                index=index,
                text=corpus[start:end],
                page=page,
                uploaded_at=uploaded_at,
                source=source,
            )
        )
    return chunks
