"""Health check used by Docker and the check scripts."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app import schemas
from backend.app.config import settings
from backend.app.database import get_db

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=schemas.HealthResponse)
def health(db: Session = Depends(get_db)) -> schemas.HealthResponse:
    """Is the API up, and can it reach the database?"""
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except SQLAlchemyError as error:
        database = f"error: {type(error).__name__}"
    return schemas.HealthResponse(status="ok", database=database, config=settings.config_name,
                                  ai_enabled=settings.ai_enabled)
