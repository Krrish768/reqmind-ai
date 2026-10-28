from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas, security
from app.deps import get_project_or_404

router = APIRouter(prefix="/projects", tags=["Projects"])

@router.post("/", response_model=schemas.ProjectResponse)
def create_project(
    project: schemas.ProjectCreate,
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    new_project = models.Project(
        name=project.name,
        description=project.description,
        company_id=current_user.company_id,
        created_by_id=current_user.id
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    return new_project


@router.get("/", response_model=list[schemas.ProjectResponse])
def list_projects(
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(models.Project).filter(
        models.Project.company_id == current_user.company_id
    ).all()


@router.get("/{project_id}", response_model=schemas.ProjectDetail)
def get_project(
    project_id: int,
    current_user: models.User = Depends(security.get_current_user),
    db: Session = Depends(get_db)
):
    return get_project_or_404(db, project_id, current_user)
