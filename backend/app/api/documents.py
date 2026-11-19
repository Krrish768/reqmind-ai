"""Upload, list, open, download and delete the documents of a project."""
from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from backend.app import models, schemas
from backend.app.api.deps import get_document_or_404, get_project_or_404
from backend.app.database import get_db
from backend.app.ingestion import storage
from backend.app.ingestion.upload import StorageUnavailable, UploadRejected, ingest_upload, remove_document
from backend.app.security import get_current_user

router = APIRouter(prefix="/projects/{project_id}/documents", tags=["Documents"])
STORAGE_DOWN = "File storage is not reachable. Start it with: docker compose up -d"


def document_in_project(db: Session, project_id: int, document_id: int, user: models.User) -> models.Document:
    """The document if it belongs to this project of the user's company, else 404."""
    get_project_or_404(db, project_id, user)
    document = get_document_or_404(db, document_id, user)
    if document.project_id != project_id:
        raise HTTPException(status_code=404, detail="Document not found in this project")
    return document


@router.post("", response_model=schemas.DocumentResponse)
async def upload_document(
    project_id: int,
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> models.Document:
    """Upload a PDF, DOCX, TXT or MD file. It is parsed and chunked right away."""
    project = get_project_or_404(db, project_id, current_user)
    data = await file.read()
    try:
        return ingest_upload(db, project, current_user, file.filename or "document.txt", data)
    except UploadRejected as error:
        raise HTTPException(status_code=400, detail=str(error))
    except StorageUnavailable as error:
        raise HTTPException(status_code=503, detail=f"{error} Start it with: docker compose up -d")


@router.get("", response_model=list[schemas.DocumentResponse])
def list_documents(
    project_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[models.Document]:
    """Documents of the project, newest first."""
    get_project_or_404(db, project_id, current_user)
    return (db.query(models.Document).filter(models.Document.project_id == project_id)
            .order_by(models.Document.id.desc()).all())


@router.get("/{document_id}", response_model=schemas.DocumentResponse)
def get_document(
    project_id: int,
    document_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> models.Document:
    """One document."""
    return document_in_project(db, project_id, document_id, current_user)


@router.get("/{document_id}/chunks", response_model=list[schemas.ChunkResponse])
def list_chunks(
    project_id: int,
    document_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[models.DocumentChunk]:
    """The text chunks of a document, in order."""
    return document_in_project(db, project_id, document_id, current_user).chunks


@router.get("/{document_id}/file")
def download_file(
    project_id: int,
    document_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """The original uploaded file."""
    document = document_in_project(db, project_id, document_id, current_user)
    try:
        data = storage.read_file(document.storage_key)
    except storage.STORAGE_ERRORS:
        raise HTTPException(status_code=503, detail=STORAGE_DOWN)
    headers = {"Content-Disposition": f'attachment; filename="{document.filename}"'}
    return Response(content=data, media_type=document.content_type or "application/octet-stream", headers=headers)


@router.delete("/{document_id}", status_code=204)
def delete_document(
    project_id: int,
    document_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Delete a document. Its requirements stay, without the document link."""
    document = document_in_project(db, project_id, document_id, current_user)
    active = db.query(models.AnalysisJob).filter(models.AnalysisJob.document_id == document.id,
                                                 models.AnalysisJob.status.in_(["queued", "running"])).first()
    if active:
        raise HTTPException(status_code=409, detail="Wait until the analysis of this document has finished")
    remove_document(db, document)
    return Response(status_code=204)
