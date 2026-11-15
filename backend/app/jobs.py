"""Analysis jobs: create the job row, put it on the Redis queue, run it.

With Redis on, a separate worker (python -m scripts.run_worker) runs the jobs
one at a time, so only one LLM job uses the GPU at once. With Redis off or
down, the API runs the job in the background of the web server instead.
"""
import logging
from datetime import datetime, timezone

from redis import Redis
from redis.exceptions import RedisError
from rq import Queue
from sqlalchemy.orm import Session

from backend.app import models
from backend.app.config import settings
from backend.app.database import SessionLocal
from backend.app.pipeline import analyze_document

WAITING_FOR_WORKER = "Waiting for the worker. Start it with: python -m scripts.run_worker"
RUNNING_IN_SERVER = "Starting inside the web server (Redis queue is off)."

logger = logging.getLogger(__name__)


def create_job(db: Session, document: models.Document) -> models.AnalysisJob:
    """Add a queued job row for the document."""
    job = models.AnalysisJob(project_id=document.project_id, document_id=document.id,
                             status="queued", progress=0, message=WAITING_FOR_WORKER)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_queue() -> Queue:
    """The RQ queue the worker listens to."""
    connection = Redis.from_url(settings.redis.url, socket_connect_timeout=3)
    return Queue(settings.redis.queue_name, connection=connection)


def enqueue(db: Session, job: models.AnalysisJob) -> bool:
    """Put the job on the Redis queue. False means the caller must run it itself."""
    if settings.redis.enabled:
        try:
            get_queue().enqueue(run_analysis_job, job.id, job_timeout=settings.analysis.job_timeout_seconds)
            return True
        except RedisError:
            pass
    job.message = RUNNING_IN_SERVER
    db.commit()
    return False


def set_progress(db: Session, job: models.AnalysisJob, percent: int, message: str) -> None:
    """Save the job's progress so the frontend can poll it."""
    job.progress = percent
    job.message = message
    db.commit()


def _finish(db: Session, job: models.AnalysisJob, status: str, message: str) -> None:
    """Mark the job as done or failed."""
    job.status = status
    job.progress = 100 if status == "done" else job.progress
    job.message = message
    job.finished_at = datetime.now(timezone.utc)
    db.commit()


def run_analysis_job(job_id: int) -> None:
    """Run one job from start to end. Called by the worker or by the API."""
    db = SessionLocal()
    try:
        job = db.get(models.AnalysisJob, job_id)
        document = db.get(models.Document, job.document_id)
        job.status = "running"
        set_progress(db, job, 1, "Reading the document")
        try:
            summary = analyze_document(db, document, lambda percent, message: set_progress(db, job, percent, message))
        except Exception as error:  # any failure must end the job, or the frontend waits forever
            db.rollback()
            document.status, document.error = "failed", str(error)
            _finish(db, job, "failed", f"Analysis failed: {error}")
            logger.exception("Analysis job %s failed", job_id)
            return
        _finish(db, job, "done", summary.message())
    finally:
        db.close()
