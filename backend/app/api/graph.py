"""OWNER: Krrish. Step 0 stub with MOCK response (shape is final)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas, security
from app.config import settings
from app.deps import get_project_or_404

router = APIRouter(tags=["Knowledge Graph"])

MOCK_GRAPH = {
    "nodes": [
        {"id": "req:1", "label": "REQ-001 User login", "type": "requirement", "data": {"priority": "high"}},
        {"id": "req:2", "label": "REQ-002 Session timeout 5 min", "type": "requirement", "data": {"priority": "medium"}},
        {"id": "ent:user", "label": "user", "type": "entity", "data": {}},
        {"id": "doc:1", "label": "sample_srs.pdf", "type": "document", "data": {}},
    ],
    "edges": [
        {"source": "req:1", "target": "ent:user", "type": "MENTIONS"},
        {"source": "req:2", "target": "ent:user", "type": "MENTIONS"},
        {"source": "doc:1", "target": "req:1", "type": "SOURCE_OF"},
        {"source": "req:1", "target": "req:2", "type": "CONFLICTS_WITH"},
    ],
}


@router.get("/projects/{project_id}/graph", response_model=schemas.GraphResponse)
def get_graph(project_id: int, refresh: bool = False,
              current_user: models.User = Depends(security.get_current_user),
              db: Session = Depends(get_db)):
    get_project_or_404(db, project_id, current_user)
    if not settings.AI_ENABLED:
        return MOCK_GRAPH
    raise NotImplementedError("Krrish: K5")
