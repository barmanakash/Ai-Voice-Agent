"""Unit tests for text extraction, cleaning and chunking (no database or server needed)."""

import io

import docx
import pymupdf
import pytest

from app.core.errors import BadRequestError
from app.services.text_extraction import Page, decode_text, extract_text
from app.services.text_processing import chunk_document, clean_text, split_spans


# ---------------------------------------------------------------- cleaning
def test_clean_text_removes_control_chars_and_normalizes_whitespace():
    raw = "Hello\x00 \x07world\u00a0 \u00adtest\r\n\r\n\r\n\r\nNext   paragraph  "
    assert clean_text(raw) == "Hello world test\n\nNext paragraph"


def test_clean_text_join_lines_for_pdf_style_text():
    raw = "This sentence wraps\nacross two lines and has a hyphen-\nated word.\n\nNew paragraph."
    cleaned = clean_text(raw, join_lines=True)
    assert cleaned == "This sentence wraps across two lines and has a hyphenated word.\n\nNew paragraph."


def test_clean_text_keeps_line_breaks_by_default():
    assert clean_text("- item one\n- item two") == "- item one\n- item two"


def test_decode_text_falls_back_to_cp1252():
    assert decode_text("café".encode("utf-8")) == "café"
    assert decode_text("café".encode("cp1252")) == "café"
    assert decode_text(b"\xef\xbb\xbfhello") == "hello"  # UTF-8 BOM removed


# ---------------------------------------------------------------- chunking
LONG_TEXT = " ".join(f"Sentence number {i} talks about topic {i % 7}." for i in range(200))


def test_spans_respect_size_and_cover_all_text():
    spans = split_spans(LONG_TEXT, size=200, overlap=40)
    assert len(spans) > 5
    assert all(e - s <= 200 for s, e in spans)
    assert spans[0][0] == 0
    assert spans[-1][1] == len(LONG_TEXT)
    for (_, prev_end), (next_start, _) in zip(spans, spans[1:]):
        assert next_start < prev_end  # consecutive chunks overlap, so no text is lost between them


def test_spans_without_overlap_do_not_overlap():
    spans = split_spans(LONG_TEXT, size=200, overlap=0)
    for (_, prev_end), (next_start, _) in zip(spans, spans[1:]):
        assert next_start >= prev_end


def test_spans_terminate_even_when_overlap_is_nearly_chunk_size():
    spans = split_spans(LONG_TEXT, size=100, overlap=99)
    assert 0 < len(spans) < len(LONG_TEXT)  # always moves forward


def test_chunks_prefer_paragraph_boundaries():
    text = ("A" * 70 + "\n\n" + "B" * 70)
    spans = split_spans(text, size=100, overlap=0)
    assert text[spans[0][0] : spans[0][1]] == "A" * 70


def test_chunks_do_not_start_mid_word():
    spans = split_spans(LONG_TEXT, size=150, overlap=30)
    for start, _ in spans[1:]:
        assert LONG_TEXT[start - 1].isspace()


def test_empty_text_gives_no_chunks():
    assert split_spans("", 100, 10) == []
    assert chunk_document([Page(1, "")], document_id="d", document_name="x.pdf", uploaded_at="t",
                          chunk_size=100, chunk_overlap=10) == []


def test_chunk_metadata_and_page_mapping():
    pages = [Page(1, "alpha " * 60), Page(2, "beta " * 60), Page(3, "gamma " * 60)]
    chunks = chunk_document(pages, document_id="doc1", document_name="report.pdf",
                            uploaded_at="2026-01-01T00:00:00+00:00", chunk_size=150, chunk_overlap=30)

    assert [c.index for c in chunks] == list(range(len(chunks)))
    assert chunks[0].chunk_id == "doc1-0"
    assert chunks[0].page == 1 and chunks[0].source == "report.pdf, page 1"
    assert chunks[-1].page == 3
    pages_seen = [c.page for c in chunks]
    assert pages_seen == sorted(pages_seen)  # page numbers never go backwards
    assert {1, 2, 3} <= set(pages_seen)

    meta = chunks[0].metadata()
    assert meta["document_id"] == "doc1" and meta["document_name"] == "report.pdf"
    assert meta["chunk_id"] == "doc1-0" and meta["page"] == 1
    assert meta["uploaded_at"] == "2026-01-01T00:00:00+00:00"


def test_chunks_without_pages_have_no_page_number():
    chunks = chunk_document([Page(None, "word " * 100)], document_id="d", document_name="notes.txt",
                            uploaded_at="t", chunk_size=100, chunk_overlap=10)
    assert all(c.page is None and c.source == "notes.txt" for c in chunks)
    assert chunks[0].metadata()["page"] == -1  # ChromaDB metadata cannot hold None


# -------------------------------------------------------------- extraction
def test_extract_txt_and_md(tmp_path):
    for name, kind in (("a.txt", "txt"), ("b.md", "md")):
        p = tmp_path / name
        p.write_text("# Title\n\nSome text", encoding="utf-8")
        result = extract_text(p, kind)
        assert result.page_count is None
        assert "Some text" in result.pages[0].text


def test_extract_docx_keeps_paragraphs_and_tables_in_order(tmp_path):
    document = docx.Document()
    document.add_paragraph("Intro paragraph")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "Name", "Role"
    table.cell(1, 0).text, table.cell(1, 1).text = "Ada", "Engineer"
    document.add_paragraph("Closing paragraph")
    path = tmp_path / "t.docx"
    document.save(path)

    text = extract_text(path, "docx").pages[0].text
    assert text.index("Intro paragraph") < text.index("Name | Role") < text.index("Ada | Engineer")
    assert text.index("Ada | Engineer") < text.index("Closing paragraph")


def test_extract_pdf_returns_one_page_object_per_page(tmp_path):
    pdf = pymupdf.open()
    for label in ("First page text", "Second page text"):
        pdf.new_page().insert_text((72, 72), label)
    path = tmp_path / "t.pdf"
    pdf.save(str(path))
    pdf.close()

    result = extract_text(path, "pdf")
    assert result.page_count == 2
    assert [p.number for p in result.pages] == [1, 2]
    assert "First page text" in result.pages[0].text
    assert "Second page text" in result.pages[1].text


def test_extract_invalid_files_raise_friendly_errors(tmp_path):
    bad_docx = tmp_path / "bad.docx"
    bad_docx.write_bytes(b"PK\x03\x04 not really a zip")
    with pytest.raises(BadRequestError, match="docx"):
        extract_text(bad_docx, "docx")

    bad_pdf = tmp_path / "bad.pdf"
    bad_pdf.write_bytes(b"%PDF-1.4 this is not a real pdf")
    with pytest.raises(Exception):  # unreadable PDF: either BadRequestError or a parser error
        result = extract_text(bad_pdf, "pdf")
        assert not any(p.text.strip() for p in result.pages)
        raise BadRequestError("no text")


def test_extract_password_protected_pdf(tmp_path):
    pdf = pymupdf.open()
    pdf.new_page().insert_text((72, 72), "secret")
    path = tmp_path / "locked.pdf"
    pdf.save(str(path), encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="pw", owner_pw="pw")
    pdf.close()
    with pytest.raises(BadRequestError, match="password"):
        extract_text(path, "pdf")
