from fastapi import APIRouter, BackgroundTasks, Depends, File, Response, UploadFile, status

from app.core.config import Config
from app.core.dependencies import (
    get_app_config,
    get_documents,
    get_file_storage,
    get_pipeline,
)
from app.core.errors import ConflictError, UnsupportedFileTypeError
from app.schemas.document import DocumentOut, DocumentStatus
from app.services.document_pipeline import DocumentPipeline
from app.services.document_service import DocumentService
from app.services.file_storage import (
    ALLOWED_EXTENSIONS,
    FileStorage,
    get_extension,
    sanitize_filename,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    config: Config = Depends(get_app_config),
    documents: DocumentService = Depends(get_documents),
    storage: FileStorage = Depends(get_file_storage),
    pipeline: DocumentPipeline = Depends(get_pipeline),
):
    """
    Validate and store an uploaded document, then process it in the background.

    Poll GET /documents/{id}/status (or GET /documents) to follow progress.
    """
    filename = sanitize_filename(file.filename)
    ext = get_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileTypeError(
            f'Unsupported file type "{ext or "unknown"}". Allowed types: PDF, DOCX, TXT, MD.'
        )

    saved = await storage.save_upload(file, ext, config.max_upload_bytes)  # size + signature checked here
    try:
        existing = await documents.find_by_hash(saved.sha256)
        if existing:
            if existing["processing_status"] != "failed":
                raise ConflictError(f'This file has already been uploaded as "{existing["filename"]}".')
            # A previous attempt failed: clear it so the user can try again with the same file.
            await pipeline.remove(existing["id"])

        stored_name = storage.finalize(saved, ext)
        try:
            document = await documents.create(
                {
                    "filename": filename,
                    "stored_name": stored_name,
                    "file_type": ext.lstrip("."),
                    "file_size": saved.size,
                    "content_hash": saved.sha256,
                }
            )
        except BaseException:
            storage.delete(stored_name)
            raise
    except BaseException:
        storage.discard(saved)  # no-op once the file has been moved
        raise

    background.add_task(pipeline.process, document["id"])
    return document


@router.get("", response_model=list[DocumentOut])
async def list_documents(documents: DocumentService = Depends(get_documents)):
    return await documents.list()


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(document_id: str, documents: DocumentService = Depends(get_documents)):
    return await documents.get(document_id)


@router.get("/{document_id}/status", response_model=DocumentStatus)
async def get_document_status(document_id: str, documents: DocumentService = Depends(get_documents)):
    return await documents.get(document_id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: str, pipeline: DocumentPipeline = Depends(get_pipeline)):
    """Delete the document, its stored file and (from Phase 6) its embeddings."""
    await pipeline.remove(document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
