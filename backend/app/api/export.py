"""Download the requirements of a project as Markdown, Word or PDF."""
import re
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from backend.app import models
from backend.app.api.deps import get_project_or_404
from backend.app.database import get_db
from backend.app.export import builders
from backend.app.security import get_current_user

router = APIRouter(tags=["Export"])

MEDIA_TYPES = {
    "md": "text/markdown; charset=utf-8",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}


def collect(db: Session, project: models.Project) -> builders.ExportData:
    """Requirements (in code order) and conflicts of the project."""
    requirements = (db.query(models.Requirement).filter(models.Requirement.project_id == project.id)
                    .order_by(models.Requirement.code).all())
    codes = {requirement.id: requirement.code for requirement in requirements}
    items = [builders.ExportRequirement(r.code, r.title, r.description, r.type, r.category, r.priority, r.status,
                                        r.ambiguity_note) for r in requirements]
    conflicts = db.query(models.RequirementConflict).filter(models.RequirementConflict.project_id == project.id)
    pairs = [builders.ExportConflict(codes.get(c.requirement_a_id, "?"), codes.get(c.requirement_b_id, "?"), c.reason)
             for c in conflicts]
    return builders.ExportData(project.name, items, pairs)


def file_name(project_name: str, extension: str) -> str:
    """"Canteen App" -> "canteen_app_requirements.pdf"."""
    slug = re.sub(r"[^a-z0-9]+", "_", project_name.lower()).strip("_") or "project"
    return f"{slug}_requirements.{extension}"


@router.get("/projects/{project_id}/export")
def export_requirements(
    project_id: int,
    file_format: Literal["md", "docx", "pdf"] = Query("md", alias="format"),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """The requirement list as a file download."""
    project = get_project_or_404(db, project_id, current_user)
    data = collect(db, project)
    if file_format == "md":
        content = builders.to_markdown(data).encode("utf-8")
    elif file_format == "docx":
        content = builders.to_docx(data)
    else:
        content = builders.to_pdf(data)
    headers = {"Content-Disposition": f'attachment; filename="{file_name(project.name, file_format)}"'}
    return Response(content=content, media_type=MEDIA_TYPES[file_format], headers=headers)
