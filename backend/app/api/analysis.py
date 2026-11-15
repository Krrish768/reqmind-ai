"""Start an analysis, poll its job, list conflicts."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app import jobs, models, schemas
from backend.app.api.deps import get_document_or_404, get_project_or_404
from backend.app.database import get_db
from backend.app.security import get_current_user

router = APIRouter(tags=["Analysis"])
READY_STATUSES = {"parsed", "analyzing", "analyzed", "failed"}


def _has_active_job(db: Session, document_id: int) -> bool:
    """True if a job for this document is still queued or running."""
    return db.query(models.AnalysisJob).filter(
        models.AnalysisJob.document_id == document_id,
        models.AnalysisJob.status.in_(["queued", "running"]),
    ).first() is not None


@router.post("/projects/{project_id}/documents/{document_id}/analyze", response_model=schemas.JobResponse)
def start_analysis(
    project_id: int,
    document_id: int,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> models.AnalysisJob:
    """Queue an analysis of one parsed document and return its job."""
    get_project_or_404(db, project_id, current_user)
    document = get_document_or_404(db, document_id, current_user)
    if document.project_id != project_id:
        raise HTTPException(status_code=404, detail="Document not found in this project")
    if _has_active_job(db, document.id):
        raise HTTPException(status_code=409, detail="This document is already being analyzed")
    if document.status not in READY_STATUSES or not document.chunks:
        raise HTTPException(status_code=409, detail="This document is not ready yet. Wait until it is parsed.")
    job = jobs.create_job(db, document)
    if not jobs.enqueue(db, job):
        background_tasks.add_task(jobs.run_analysis_job, job.id)
    return job


@router.get("/jobs/{job_id}", response_model=schemas.JobResponse)
def get_job(
    job_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> models.AnalysisJob:
    """Status and progress of one job."""
    job = db.get(models.AnalysisJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    get_project_or_404(db, job.project_id, current_user)
    return job


@router.get("/projects/{project_id}/jobs", response_model=list[schemas.JobResponse])
def list_jobs(
    project_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[models.AnalysisJob]:
    """All jobs of a project, newest first."""
    get_project_or_404(db, project_id, current_user)
    return (db.query(models.AnalysisJob).filter(models.AnalysisJob.project_id == project_id)
            .order_by(models.AnalysisJob.id.desc()).all())


@router.get("/projects/{project_id}/conflicts", response_model=list[schemas.ConflictResponse])
def list_conflicts(
    project_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[models.RequirementConflict]:
    """Conflicting requirement pairs of a project."""
    get_project_or_404(db, project_id, current_user)
    return (db.query(models.RequirementConflict).filter(models.RequirementConflict.project_id == project_id)
            .order_by(models.RequirementConflict.id).all())
