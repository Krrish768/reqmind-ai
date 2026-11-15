"""Shared route helpers. Every lookup is limited to the user's own company."""
import re

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app import models

CODE_PATTERN = re.compile(r"REQ-(\d+)")


def get_project_or_404(db: Session, project_id: int, user: models.User) -> models.Project:
    """Return the project if it belongs to the user's company, else answer 404."""
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.company_id == user.company_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def get_document_or_404(db: Session, document_id: int, user: models.User) -> models.Document:
    """Return the document if it belongs to the user's company, else answer 404."""
    document = db.query(models.Document).filter(
        models.Document.id == document_id,
        models.Document.company_id == user.company_id,
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def get_requirement_or_404(db: Session, requirement_id: int, user: models.User) -> models.Requirement:
    """Return the requirement if it belongs to the user's company, else answer 404."""
    requirement = db.query(models.Requirement).filter(
        models.Requirement.id == requirement_id,
        models.Requirement.company_id == user.company_id,
    ).first()
    if not requirement:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return requirement


def next_requirement_code(db: Session, project_id: int) -> str:
    """Next free code in the project: REQ-001, REQ-002 ...

    Uses the highest number so far, so codes stay unique after deletes.
    Call it right before adding each requirement to the session.
    """
    codes = db.query(models.Requirement.code).filter(models.Requirement.project_id == project_id).all()
    highest = 0
    for (code,) in codes:
        match = CODE_PATTERN.fullmatch(code or "")
        if match:
            highest = max(highest, int(match.group(1)))
    return f"REQ-{highest + 1:03d}"
