"""Phase 5 tests: document upload, validation, processing, duplicates and deletion.

Uses a temporary uploads folder and an in-memory document store, so no MongoDB is needed.
"""

import asyncio
import io

import docx
import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.core.config import Config
from app.core.dependencies import (
    get_app_config,
    get_documents,
    get_file_storage,
    get_pipeline,
    get_settings_service,
)
from app.main import app
from app.schemas.settings import RuntimeSettings
from app.services.document_pipeline import DocumentPipeline
from app.services.file_storage import FileStorage
from app.services.settings_service import SettingsService
from tests.fakes_documents import InMemoryDocuments

SAMPLE_TEXT = "Aria is a local assistant. " * 120  # ~3 KB


@pytest.fixture
def env(tmp_path):
    uploads = tmp_path / "uploads"
    store = InMemoryDocuments()
    storage = FileStorage(uploads)
    settings = SettingsService(tmp_path / "settings.json", RuntimeSettings(model="m"))
    pipeline = DocumentPipeline(store, storage, settings, indexer=None, max_concurrent=2)
    config = Config(max_upload_mb=1)

    app.dependency_overrides[get_documents] = lambda: store
    app.dependency_overrides[get_file_storage] = lambda: storage
    app.dependency_overrides[get_pipeline] = lambda: pipeline
    app.dependency_overrides[get_settings_service] = lambda: settings
    app.dependency_overrides[get_app_config] = lambda: config
    yield TestClient(app), store, uploads, settings
    app.dependency_overrides.clear()


def upload(client, name, content, mime="application/octet-stream"):
    return client.post("/api/documents/upload", files={"file": (name, content, mime)})


def stored_files(uploads):
    return [p.name for p in uploads.iterdir()]


def make_docx() -> bytes:
    document = docx.Document()
    document.add_paragraph("Quarterly report. " * 30)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def make_pdf(pages=2) -> bytes:
    pdf = pymupdf.open()
    for i in range(pages):
        pdf.new_page().insert_text((72, 72), f"Content of page {i + 1} for the knowledge base.")
    data = pdf.tobytes()
    pdf.close()
    return data


# ------------------------------------------------------------ happy paths
def test_upload_txt_is_accepted_then_processed(env):
    client, _, uploads, _ = env
    r = upload(client, "notes.txt", SAMPLE_TEXT.encode())
    assert r.status_code == 202
    body = r.json()
    assert body["filename"] == "notes.txt" and body["file_type"] == "txt"
    assert body["processing_status"] == "pending"
    assert "stored_name" not in body and "content_hash" not in body  # internals stay private

    doc = client.get(f"/api/documents/{body['id']}").json()
    assert doc["processing_status"] == "completed"
    assert doc["progress"] == 100
    assert doc["chunk_count"] >= 3
    assert doc["char_count"] > 0
    assert doc["text_preview"].startswith("Aria is a local assistant")
    assert doc["processed_at"] is not None

    assert len(stored_files(uploads)) == 1  # one stored file, no temp leftovers


def test_upload_markdown(env):
    client, *_ = env
    r = upload(client, "readme.md", b"# Title\n\nSome *markdown* content that is long enough to keep.")
    doc = client.get(f"/api/documents/{r.json()['id']}").json()
    assert doc["file_type"] == "md" and doc["processing_status"] == "completed"


def test_upload_docx(env):
    client, *_ = env
    r = upload(client, "report.docx", make_docx())
    assert r.status_code == 202
    doc = client.get(f"/api/documents/{r.json()['id']}").json()
    assert doc["processing_status"] == "completed" and doc["chunk_count"] >= 1
    assert "Quarterly report" in doc["text_preview"]


def test_upload_pdf_reports_page_count(env):
    client, *_ = env
    r = upload(client, "paper.pdf", make_pdf(pages=3))
    doc = client.get(f"/api/documents/{r.json()['id']}").json()
    assert doc["processing_status"] == "completed"
    assert doc["page_count"] == 3
    assert "Content of page 1" in doc["text_preview"]


def test_chunk_settings_are_applied(env):
    client, _, _, settings = env
    current = settings.get()
    small = current.model_copy(update={"rag": current.rag.model_copy(update={"chunk_size": 200, "chunk_overlap": 20})})
    asyncio.run(settings.update(small))
    r = upload(client, "long.txt", SAMPLE_TEXT.encode())
    doc = client.get(f"/api/documents/{r.json()['id']}").json()
    assert doc["chunk_count"] > 10


def test_list_and_status_endpoints(env):
    client, *_ = env
    a = upload(client, "a.txt", b"first document " * 30).json()
    b = upload(client, "b.txt", b"second document " * 30).json()

    listed = client.get("/api/documents").json()
    assert [d["id"] for d in listed] == [b["id"], a["id"]]  # newest first

    status = client.get(f"/api/documents/{a['id']}/status").json()
    assert status == {"id": a["id"], "processing_status": "completed", "progress": 100,
                      "chunk_count": status["chunk_count"], "error": None}


# ------------------------------------------------------------- validation
def test_unsupported_extension_is_415(env):
    client, _, uploads, _ = env
    r = upload(client, "malware.exe", b"MZ....")
    assert r.status_code == 415
    assert "Unsupported file type" in r.json()["detail"]
    assert stored_files(uploads) == []


def test_missing_extension_is_415(env):
    client, *_ = env
    assert upload(client, "README", b"text").status_code == 415


@pytest.mark.parametrize(
    "name,content",
    [
        ("fake.pdf", b"just some text pretending to be a pdf"),
        ("fake.docx", b"just some text pretending to be a docx"),
        ("binary.txt", b"hello\x00\x01\x02world"),
    ],
)
def test_content_must_match_extension(env, name, content):
    client, _, uploads, _ = env
    r = upload(client, name, content)
    assert r.status_code == 400
    assert stored_files(uploads) == []  # nothing left behind


def test_empty_file_is_400(env):
    client, _, uploads, _ = env
    assert upload(client, "empty.txt", b"").status_code == 400
    assert stored_files(uploads) == []


def test_file_over_limit_is_413_and_cleaned_up(env):
    client, _, uploads, _ = env  # limit is 1 MB in this fixture
    r = upload(client, "big.txt", b"a" * (1024 * 1024 + 1))
    assert r.status_code == 413
    assert "limit" in r.json()["detail"]
    assert stored_files(uploads) == []


def test_file_exactly_at_limit_is_accepted(env):
    client, *_ = env
    assert upload(client, "max.txt", b"a " * (512 * 1024)).status_code == 202


def test_filename_path_is_sanitized(env):
    client, _, uploads, _ = env
    r = upload(client, "../../evil.txt", b"harmless content " * 20)
    assert r.status_code == 202
    assert r.json()["filename"] == "evil.txt"
    files = stored_files(uploads)
    assert len(files) == 1 and files[0].endswith(".txt") and files[0] != "evil.txt"  # server-generated name


# ------------------------------------------------------------- duplicates
def test_duplicate_content_is_rejected_even_if_renamed(env):
    client, _, uploads, _ = env
    assert upload(client, "one.txt", b"same content " * 20).status_code == 202
    r = upload(client, "renamed.txt", b"same content " * 20)
    assert r.status_code == 409
    assert "already been uploaded" in r.json()["detail"]
    assert len(stored_files(uploads)) == 1
    assert len(client.get("/api/documents").json()) == 1


# --------------------------------------------------------- failed processing
def test_document_without_text_fails_with_helpful_message(env):
    client, *_ = env
    r = upload(client, "blank.txt", b"   \n\n   \n")
    doc = client.get(f"/api/documents/{r.json()['id']}").json()
    assert doc["processing_status"] == "failed"
    assert "No readable text" in doc["error"]


def test_corrupt_docx_fails_cleanly(env):
    client, *_ = env
    r = upload(client, "broken.docx", b"PK\x03\x04 this is not a valid archive")
    assert r.status_code == 202  # passes the quick signature check, fails during processing
    doc = client.get(f"/api/documents/{r.json()['id']}").json()
    assert doc["processing_status"] == "failed"
    assert "docx" in doc["error"]


def test_failed_document_can_be_uploaded_again(env):
    client, _, uploads, _ = env
    first = upload(client, "blank.txt", b"   \n  ").json()
    assert client.get(f"/api/documents/{first['id']}").json()["processing_status"] == "failed"

    second = upload(client, "blank.txt", b"   \n  ")
    assert second.status_code == 202  # not blocked as a duplicate
    assert second.json()["id"] != first["id"]
    assert len(client.get("/api/documents").json()) == 1  # old failed record was replaced
    assert len(stored_files(uploads)) == 1


def test_interrupted_documents_are_marked_failed_on_restart(env):
    client, store, *_ = env
    doc = asyncio.run(store.create({"filename": "x.txt", "stored_name": "x.txt", "file_type": "txt",
                                    "file_size": 1, "content_hash": "abc"}))
    asyncio.run(store.update(doc["id"], processing_status="processing", progress=40))

    assert asyncio.run(store.fail_unfinished("interrupted")) == 1
    shown = client.get(f"/api/documents/{doc['id']}").json()
    assert shown["processing_status"] == "failed" and shown["error"] == "interrupted"


# ----------------------------------------------------------------- delete
def test_delete_removes_record_and_file(env):
    client, _, uploads, _ = env
    doc = upload(client, "gone.txt", b"delete me " * 30).json()
    assert len(stored_files(uploads)) == 1

    assert client.delete(f"/api/documents/{doc['id']}").status_code == 204
    assert stored_files(uploads) == []
    assert client.get(f"/api/documents/{doc['id']}").status_code == 404
    assert client.get("/api/documents").json() == []


def test_deleted_document_can_be_uploaded_again(env):
    client, *_ = env
    doc = upload(client, "again.txt", b"re-upload me " * 30).json()
    client.delete(f"/api/documents/{doc['id']}")
    assert upload(client, "again.txt", b"re-upload me " * 30).status_code == 202


def test_delete_unknown_or_invalid_id_is_404(env):
    client, *_ = env
    assert client.delete("/api/documents/" + "f" * 24).status_code == 404
    assert client.delete("/api/documents/not-an-id").status_code == 404
    assert client.get("/api/documents/not-an-id/status").status_code == 404
