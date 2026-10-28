"""Shared helpers (Step 0). Both of you import from here. Don't rename functions."""
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app import models


def get_project_or_404(db: Session, project_id: int, user: models.User) -> models.Project:
    """Return project only if it belongs to the user's company (multi-tenant check)."""
    project = db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.company_id == user.company_id,
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def get_document_or_404(db: Session, document_id: int, user: models.User) -> models.Document:
    document = db.query(models.Document).filter(
        models.Document.id == document_id,
        models.Document.company_id == user.company_id,
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def get_requirement_or_404(db: Session, requirement_id: int, user: models.User) -> models.Requirement:
    req = db.query(models.Requirement).filter(
        models.Requirement.id == requirement_id,
        models.Requirement.company_id == user.company_id,
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return req


def next_requirement_code(db: Session, project_id: int) -> str:
    """REQ-001, REQ-002 ... per project. Call right before inserting each Requirement."""
    count = db.query(models.Requirement).filter(models.Requirement.project_id == project_id).count()
    return f"REQ-{count + 1:03d}"
