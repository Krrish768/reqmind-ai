"""Write the requirement list of a project as Markdown, Word or PDF.

Every format has the same content: a summary table, the requirements grouped
by type, and the conflicts with their reason.

Example:
    python -m backend.app.export.builders
"""
import io
from dataclasses import dataclass
from datetime import date
from xml.sax.saxutils import escape

import docx
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer

TYPE_TITLES = {"functional": "Functional", "non_functional": "Non-functional", "constraint": "Constraints"}


@dataclass
class ExportRequirement:
    code: str
    title: str
    description: str
    type: str
    category: str | None
    priority: str
    status: str
    ambiguity_note: str | None


@dataclass
class ExportConflict:
    code_a: str
    code_b: str
    reason: str


@dataclass
class ExportData:
    project_name: str
    requirements: list[ExportRequirement]
    conflicts: list[ExportConflict]


def summary_rows(data: ExportData) -> list[tuple[str, str]]:
    """(label, count) lines for the summary."""
    rows = [("Requirements", str(len(data.requirements)))]
    for type_key, title in TYPE_TITLES.items():
        rows.append((title, str(sum(1 for item in data.requirements if item.type == type_key))))
    rows.append(("Flagged as vague", str(sum(1 for item in data.requirements if item.ambiguity_note))))
    rows.append(("Conflicts", str(len(data.conflicts))))
    return rows


def grouped(data: ExportData) -> list[tuple[str, list[ExportRequirement]]]:
    """Requirements by type, in a fixed order, skipping empty groups."""
    groups = []
    for type_key, title in TYPE_TITLES.items():
        items = [item for item in data.requirements if item.type == type_key]
        if items:
            groups.append((title, items))
    return groups


def meta_line(item: ExportRequirement) -> str:
    """"Priority: high · Category: security · Status: draft"."""
    parts = [f"Priority: {item.priority}", f"Category: {item.category or 'other'}", f"Status: {item.status}"]
    return " · ".join(parts)


def to_markdown(data: ExportData) -> str:
    """The export as a Markdown document."""
    lines = [f"# {data.project_name}: requirements", "", f"Exported on {date.today().isoformat()}.", "",
             "| | Count |", "|---|---|"]
    lines += [f"| {label} | {count} |" for label, count in summary_rows(data)]
    for title, items in grouped(data):
        lines += ["", f"## {title}"]
        for item in items:
            lines += ["", f"### {item.code} {item.title}", "", item.description, "", meta_line(item)]
            if item.ambiguity_note:
                lines += ["", f"Note: {item.ambiguity_note}"]
    lines += ["", "## Conflicts", ""]
    lines += [f"- **{c.code_a} / {c.code_b}**: {c.reason}" for c in data.conflicts] or ["No conflicts found."]
    return "\n".join(lines) + "\n"


def to_docx(data: ExportData) -> bytes:
    """The export as a Word file."""
    document = docx.Document()
    document.add_heading(f"{data.project_name}: requirements", level=0)
    document.add_paragraph(f"Exported on {date.today().isoformat()}.")
    table = document.add_table(rows=0, cols=2)
    table.style = "Light Grid Accent 1"
    for label, count in summary_rows(data):
        cells = table.add_row().cells
        cells[0].text, cells[1].text = label, count
    for title, items in grouped(data):
        document.add_heading(title, level=1)
        for item in items:
            document.add_heading(f"{item.code} {item.title}", level=2)
            document.add_paragraph(item.description)
            document.add_paragraph().add_run(meta_line(item)).italic = True
            if item.ambiguity_note:
                document.add_paragraph(f"Note: {item.ambiguity_note}")
    document.add_heading("Conflicts", level=1)
    for conflict in data.conflicts:
        document.add_paragraph(f"{conflict.code_a} / {conflict.code_b}: {conflict.reason}", style="List Bullet")
    if not data.conflicts:
        document.add_paragraph("No conflicts found.")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _pdf_story(data: ExportData) -> list[Flowable]:
    """ReportLab flowables for the PDF."""
    styles = getSampleStyleSheet()
    story = [Paragraph(escape(f"{data.project_name}: requirements"), styles["Title"]),
             Paragraph(f"Exported on {date.today().isoformat()}.", styles["Normal"]), Spacer(1, 0.4 * cm)]
    story += [Paragraph(f"{label}: <b>{count}</b>", styles["Normal"]) for label, count in summary_rows(data)]
    for title, items in grouped(data):
        story.append(Paragraph(title, styles["Heading1"]))
        for item in items:
            story.append(Paragraph(escape(f"{item.code} {item.title}"), styles["Heading3"]))
            story.append(Paragraph(escape(item.description), styles["Normal"]))
            story.append(Paragraph(f"<i>{escape(meta_line(item))}</i>", styles["Normal"]))
            if item.ambiguity_note:
                story.append(Paragraph(escape(f"Note: {item.ambiguity_note}"), styles["Normal"]))
    story.append(Paragraph("Conflicts", styles["Heading1"]))
    for conflict in data.conflicts:
        story.append(Paragraph(escape(f"{conflict.code_a} / {conflict.code_b}: {conflict.reason}"), styles["Normal"]))
    if not data.conflicts:
        story.append(Paragraph("No conflicts found.", styles["Normal"]))
    return story


def to_pdf(data: ExportData) -> bytes:
    """The export as a PDF file (A4)."""
    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=A4, title=f"{data.project_name} requirements",
                            leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
    pdf.build(_pdf_story(data))
    return buffer.getvalue()


if __name__ == "__main__":
    demo = ExportData("Demo", [ExportRequirement("REQ-001", "Lock account", "The system shall lock the account.",
                                                 "functional", "security", "high", "draft", None)], [])
    print(to_markdown(demo))
    print(f"docx: {len(to_docx(demo))} bytes, pdf: {len(to_pdf(demo))} bytes")
