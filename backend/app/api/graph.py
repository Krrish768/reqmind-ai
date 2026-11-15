"""The knowledge graph of a project, from Neo4j or (fallback) from Postgres."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app import models, schemas
from backend.app.api.deps import get_project_or_404
from backend.app.config import settings
from backend.app.database import get_db
from backend.app.knowledge_graph import builder, neo4j_store
from backend.app.security import get_current_user

router = APIRouter(tags=["Knowledge Graph"])


@router.get("/projects/{project_id}/graph", response_model=schemas.GraphResponse)
def get_graph(
    project_id: int,
    refresh: bool = False,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> schemas.GraphResponse:
    """Nodes and edges of the project. refresh=true copies Postgres to Neo4j first."""
    project = get_project_or_404(db, project_id, current_user)
    if not settings.neo4j.enabled:
        return builder.build_graph(db, project)
    try:
        if refresh:
            nodes, edges = builder.graph_elements(db, project)
            neo4j_store.sync_project(project.id, project.company_id, nodes, edges)
        return neo4j_store.read_project(project.id, project.company_id)
    except neo4j_store.NEO4J_ERRORS:
        return builder.build_graph(db, project)
