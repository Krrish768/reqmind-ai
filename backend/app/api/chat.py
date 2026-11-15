"""Ask a question about a project's documents."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app import models, schemas
from backend.app.api.deps import get_project_or_404
from backend.app.database import get_db
from backend.app.rag.chat import answer_question
from backend.app.security import get_current_user

router = APIRouter(tags=["Chat"])


@router.post("/projects/{project_id}/chat", response_model=schemas.ChatResponse)
def chat(
    project_id: int,
    body: schemas.ChatRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.ChatResponse:
    """Answer from the project's passages, with the passages used as sources."""
    project = get_project_or_404(db, project_id, current_user)
    return answer_question(db, project, body.question.strip())
