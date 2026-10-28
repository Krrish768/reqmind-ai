"""OWNER: Krrish. Step 0 stub with MOCK response (shape is final)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas, security
from app.config import settings
from app.deps import get_project_or_404

router = APIRouter(tags=["Chat"])


@router.post("/projects/{project_id}/chat", response_model=schemas.ChatResponse)
def chat(project_id: int, body: schemas.ChatRequest,
         current_user: models.User = Depends(security.get_current_user),
         db: Session = Depends(get_db)):
    get_project_or_404(db, project_id, current_user)
    if not settings.AI_ENABLED:
        return {"answer": f"(mock) AI is disabled on this machine. You asked: {body.question}",
                "sources": [{"document_id": 1, "filename": "sample_srs.pdf", "chunk_index": 0,
                             "text": "The system shall allow users to log in with email and password."}]}
    raise NotImplementedError("Krrish: K6")
