"""Create, list and open projects of the user's company."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app import models, schemas
from backend.app.api.deps import get_project_or_404
from backend.app.database import get_db
from backend.app.security import get_current_user

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("", response_model=schemas.ProjectResponse)
def create_project(
    body: schemas.ProjectCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> models.Project:
    """Create a project in the user's company."""
    project = models.Project(
        name=body.name,
        description=body.description,
        company_id=current_user.company_id,
        created_by_id=current_user.id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


@router.get("", response_model=list[schemas.ProjectResponse])
def list_projects(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[models.Project]:
    """List the projects of the user's company, newest first."""
    return (
        db.query(models.Project)
        .filter(models.Project.company_id == current_user.company_id)
        .order_by(models.Project.id.desc())
        .all()
    )


@router.get("/{project_id}", response_model=schemas.ProjectDetail)
def get_project(
    project_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> models.Project:
    """Return one project."""
    return get_project_or_404(db, project_id, current_user)
