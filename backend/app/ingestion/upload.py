"""Save an uploaded file, read its text and store the chunks; or remove a document.

After a successful upload the document has status "parsed" and its chunks are
in the database, ready for the analysis. A file without readable text is kept
with status "failed" and the reason in `error`.
"""
import logging
import uuid

from sqlalchemy.orm import Session

from backend.app import models
from backend.app.config import settings
from backend.app.ingestion import chunking, parsing, storage
from backend.app.rag import vector_store

logger = logging.getLogger(__name__)


class UploadRejected(Exception):
    """The file is too big, empty or of a type we cannot read."""


class StorageUnavailable(Exception):
    """The file store could not be reached."""


def check_upload(filename: str, data: bytes) -> None:
    """Refuse empty, too big or unsupported files before anything is saved."""
    max_bytes = settings.ingestion.max_upload_mb * 1024 * 1024
    if not data:
        raise UploadRejected("The file is empty.")
    if len(data) > max_bytes:
        raise UploadRejected(f"The file is larger than {settings.ingestion.max_upload_mb} MB.")
    if parsing.extension_of(filename) not in parsing.ALLOWED_EXTENSIONS:
        raise UploadRejected("We can read PDF, DOCX, TXT and MD files.")


def store_file(project: models.Project, filename: str, data: bytes) -> tuple[str, str]:
    """Save the bytes in the file store. Returns (storage_key, content_type)."""
    extension = parsing.extension_of(filename)
    key = f"{project.company_id}/{project.id}/{uuid.uuid4().hex}{extension}"
    content_type = parsing.CONTENT_TYPES[extension]
    try:
        storage.save_file(key, data, content_type)
    except storage.STORAGE_ERRORS as error:
        raise StorageUnavailable(f"File storage is not reachable ({type(error).__name__}).") from error
    return key, content_type


def save_chunks(db: Session, document: models.Document, data: bytes) -> None:
    """Parse the file and add its chunks; mark the document parsed or failed."""
    try:
        pages = parsing.parse_file(document.filename, data)
    except parsing.ParseError as error:
        document.status, document.error = "failed", str(error)
        return
    chunks = chunking.chunk_pages(pages, settings.ingestion.chunk_chars, settings.ingestion.overlap_chars)
    for chunk in chunks:
        db.add(models.DocumentChunk(document_id=document.id, chunk_index=chunk.chunk_index, text=chunk.text,
                                    page=chunk.page, char_start=chunk.char_start, char_end=chunk.char_end))
    document.status, document.error = "parsed", None


def ingest_upload(db: Session, project: models.Project, user: models.User, filename: str,
                  data: bytes) -> models.Document:
    """Check, store, parse and chunk one uploaded file.

    Raises:
        UploadRejected: The file cannot be accepted.
        StorageUnavailable: The file store is down.
    """
    check_upload(filename, data)
    key, content_type = store_file(project, filename, data)
    document = models.Document(project_id=project.id, company_id=project.company_id, uploaded_by_id=user.id,
                               filename=filename, content_type=content_type, storage_key=key,
                               size_bytes=len(data), status="uploaded")
    db.add(document)
    db.flush()
    save_chunks(db, document, data)
    db.commit()
    db.refresh(document)
    return document


def remove_document(db: Session, document: models.Document) -> None:
    """Delete the document, its chunks, its file and its search vectors.

    Requirements found in it stay, with their document link cleared.
    """
    db.query(models.Requirement).filter(models.Requirement.document_id == document.id).update(
        {models.Requirement.document_id: None, models.Requirement.source_chunk_id: None},
        synchronize_session=False)
    for table in (models.AnalysisJob, models.DocumentChunk):
        db.query(table).filter(table.document_id == document.id).delete(synchronize_session=False)
    try:
        storage.delete_file(document.storage_key)
    except storage.STORAGE_ERRORS as error:
        logger.warning("Could not delete file %s: %s", document.storage_key, error)
    if settings.qdrant.enabled:
        try:
            vector_store.delete_document(document.id)
        except vector_store.QDRANT_ERRORS as error:
            logger.warning("Could not delete vectors of document %s: %s", document.id, error)
    db.delete(document)
    db.commit()
