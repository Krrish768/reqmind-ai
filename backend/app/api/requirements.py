"""List, add, edit and delete the requirements of a project."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from backend.app import models, schemas
from backend.app.api.deps import get_project_or_404, get_requirement_or_404, next_requirement_code
from backend.app.database import get_db
from backend.app.security import get_current_user

router = APIRouter(prefix="/projects/{project_id}/requirements", tags=["Requirements"])


def requirement_in_project(db: Session, project_id: int, requirement_id: int,
                           user: models.User) -> models.Requirement:
    """The requirement if it belongs to this project of the user's company, else 404."""
    get_project_or_404(db, project_id, user)
    requirement = get_requirement_or_404(db, requirement_id, user)
    if requirement.project_id != project_id:
        raise HTTPException(status_code=404, detail="Requirement not found in this project")
    return requirement


@router.get("", response_model=list[schemas.RequirementResponse])
def list_requirements(
    project_id: int,
    status: schemas.ReqStatus | None = None,
    requirement_type: schemas.RequirementType | None = Query(None, alias="type"),
    document_id: int | None = None,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[models.Requirement]:
    """Requirements of the project in code order, with optional filters."""
    get_project_or_404(db, project_id, current_user)
    query = db.query(models.Requirement).filter(models.Requirement.project_id == project_id)
    if status:
        query = query.filter(models.Requirement.status == status)
    if requirement_type:
        query = query.filter(models.Requirement.type == requirement_type)
    if document_id is not None:
        query = query.filter(models.Requirement.document_id == document_id)
    return query.order_by(models.Requirement.code).all()


@router.post("", response_model=schemas.RequirementResponse)
def create_requirement(
    project_id: int,
    body: schemas.RequirementCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> models.Requirement:
    """Add a requirement by hand."""
    project = get_project_or_404(db, project_id, current_user)
    requirement = models.Requirement(
        project_id=project.id, company_id=project.company_id, code=next_requirement_code(db, project.id),
        title=body.title, description=body.description, type=body.type, category=body.category,
        priority=body.priority, entities=body.entities, status="draft", created_by="user",
    )
    db.add(requirement)
    db.commit()
    db.refresh(requirement)
    return requirement


@router.patch("/{requirement_id}", response_model=schemas.RequirementResponse)
def update_requirement(
    project_id: int,
    requirement_id: int,
    body: schemas.RequirementUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> models.Requirement:
    """Change only the fields that were sent."""
    requirement = requirement_in_project(db, project_id, requirement_id, current_user)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(requirement, field, value)
    db.commit()
    db.refresh(requirement)
    return requirement


@router.delete("/{requirement_id}", status_code=204)
def delete_requirement(
    project_id: int,
    requirement_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Delete a requirement and the conflicts it is part of."""
    requirement = requirement_in_project(db, project_id, requirement_id, current_user)
    db.query(models.RequirementConflict).filter(
        (models.RequirementConflict.requirement_a_id == requirement.id)
        | (models.RequirementConflict.requirement_b_id == requirement.id)
    ).delete(synchronize_session=False)
    db.delete(requirement)
    db.commit()
    return Response(status_code=204)
