"""OWNER: Krrish. Step 0 stub with MOCK responses (shape is final).
Keep the `if not settings.AI_ENABLED` mock branch forever - Muskaan's machine depends on it."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas, security
from app.config import settings
from app.deps import get_project_or_404, get_document_or_404

router = APIRouter(tags=["Analysis"])

MOCK_JOB = {"id": 0, "project_id": 0, "document_id": 0, "status": "done", "progress": 100,
            "message": "AI disabled on this machine (mock job)"}


@router.post("/projects/{project_id}/documents/{document_id}/analyze", response_model=schemas.JobResponse)
def start_analysis(project_id: int, document_id: int,
                   current_user: models.User = Depends(security.get_current_user),
                   db: Session = Depends(get_db)):
    get_project_or_404(db, project_id, current_user)
    get_document_or_404(db, document_id, current_user)
    if not settings.AI_ENABLED:
        return {**MOCK_JOB, "project_id": project_id, "document_id": document_id}
    raise NotImplementedError("Krrish: K4")


@router.get("/jobs/{job_id}", response_model=schemas.JobResponse)
def get_job(job_id: int, current_user: models.User = Depends(security.get_current_user),
            db: Session = Depends(get_db)):
    if not settings.AI_ENABLED or job_id == 0:
        return MOCK_JOB
    raise NotImplementedError("Krrish: K4")


@router.get("/projects/{project_id}/conflicts", response_model=list[schemas.ConflictResponse])
def list_conflicts(project_id: int, current_user: models.User = Depends(security.get_current_user),
                   db: Session = Depends(get_db)):
    get_project_or_404(db, project_id, current_user)
    return db.query(models.RequirementConflict).filter(
        models.RequirementConflict.project_id == project_id).all()
