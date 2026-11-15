"""Run the full analysis for one document.

Steps: read its chunks -> agents workflow -> save requirements and conflicts ->
index chunks in Qdrant -> copy the project graph to Neo4j. Qdrant and Neo4j
problems do not stop the job; they are written into the job message.

Example (needs a document with chunks in the database):
    python -m scripts.analyze_document --document-id 1
"""
from collections.abc import Callable
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from backend.app import models
from backend.app.agents.workflow import run_workflow
from backend.app.api.deps import next_requirement_code
from backend.app.config import settings
from backend.app.knowledge_graph import builder, neo4j_store
from backend.app.llm import client as llm
from backend.app.rag import vector_store
from backend.app.schemas import ChunkIn, FoundConflict, FoundRequirement

ProgressFn = Callable[[int, str], None]


@dataclass
class AnalysisSummary:
    requirements: int
    conflicts: int
    method: str
    notes: list[str] = field(default_factory=list)

    def message(self) -> str:
        """One line for the job: counts plus any notes."""
        text = f"Found {self.requirements} requirements and {self.conflicts} conflicts ({self.method})."
        return " ".join([text, *self.notes])


def load_chunks(db: Session, document: models.Document) -> list[ChunkIn]:
    """The document's chunks in order, at most analysis.max_chunks."""
    chunks = (
        db.query(models.DocumentChunk)
        .filter(models.DocumentChunk.document_id == document.id)
        .order_by(models.DocumentChunk.chunk_index)
        .limit(settings.analysis.max_chunks)
        .all()
    )
    return [ChunkIn(chunk_id=chunk.id, chunk_index=chunk.chunk_index, text=chunk.text, page=chunk.page)
            for chunk in chunks]


def delete_old_results(db: Session, document: models.Document) -> None:
    """Remove AI requirements of this document and their conflicts (before saving new ones)."""
    old_ids = [row.id for row in db.query(models.Requirement.id).filter(
        models.Requirement.document_id == document.id, models.Requirement.created_by == "ai")]
    if not old_ids:
        return
    db.query(models.RequirementConflict).filter(
        models.RequirementConflict.requirement_a_id.in_(old_ids)
        | models.RequirementConflict.requirement_b_id.in_(old_ids)
    ).delete(synchronize_session=False)
    db.query(models.Requirement).filter(models.Requirement.id.in_(old_ids)).delete(synchronize_session=False)
    db.flush()


def _new_requirement(db: Session, document: models.Document, item: FoundRequirement) -> models.Requirement:
    """A Requirement row from a found item (not yet committed)."""
    return models.Requirement(
        project_id=document.project_id, company_id=document.company_id, document_id=document.id,
        source_chunk_id=item.chunk_id, code=next_requirement_code(db, document.project_id),
        title=item.title, description=item.description, type=item.type, category=item.category,
        priority=item.priority, status="draft", is_ambiguous=item.is_ambiguous,
        ambiguity_note=item.ambiguity_note, entities=item.entities, created_by="ai",
    )


def save_results(db: Session, document: models.Document, found: list[FoundRequirement],
                 conflicts: list[FoundConflict]) -> None:
    """Replace the document's AI requirements and conflicts with the new ones."""
    delete_old_results(db, document)
    rows = []
    for item in found:
        row = _new_requirement(db, document, item)
        db.add(row)
        db.flush()  # gives row.id, and the next code sees this row
        rows.append(row)
    for conflict in conflicts:
        db.add(models.RequirementConflict(
            project_id=document.project_id, requirement_a_id=rows[conflict.index_a].id,
            requirement_b_id=rows[conflict.index_b].id, reason=conflict.reason))
    db.commit()


def index_chunks(document: models.Document, chunks: list[ChunkIn]) -> str | None:
    """Embed the chunks and store them in Qdrant. Returns a note on failure."""
    if not (settings.ai_enabled and settings.qdrant.enabled):
        return None
    try:
        vectors = llm.embed_texts([chunk.text for chunk in chunks])
        vector_store.delete_document(document.id)
        payloads = [{"chunk_id": chunk.chunk_id, "document_id": document.id, "project_id": document.project_id,
                     "company_id": document.company_id, "chunk_index": chunk.chunk_index,
                     "filename": document.filename, "text": chunk.text} for chunk in chunks]
        vector_store.index_chunks(payloads, vectors)
    except (llm.LlmUnavailable, *vector_store.QDRANT_ERRORS) as error:
        return f"Chat search index not updated ({type(error).__name__}), chat will use keyword search."
    return None


def sync_graph(db: Session, project: models.Project) -> str | None:
    """Copy the project graph into Neo4j. Returns a note on failure."""
    if not settings.neo4j.enabled:
        return None
    nodes, edges = builder.graph_elements(db, project)
    try:
        neo4j_store.sync_project(project.id, project.company_id, nodes, edges)
    except neo4j_store.NEO4J_ERRORS as error:
        return f"Neo4j not updated ({type(error).__name__}), the graph is read from the database."
    return None


def analyze_document(db: Session, document: models.Document, report: ProgressFn) -> AnalysisSummary:
    """Run every step for one document and return what was found.

    Args:
        db: Open session.
        document: A document whose chunks are already saved.
        report: Called with (percent, message).

    Returns:
        Counts, the method used ("llm" or "rules") and notes about skipped steps.
    """
    chunks = load_chunks(db, document)
    if not chunks:
        raise ValueError("This document has no text chunks. Upload and parse it first.")
    document.status, document.error = "analyzing", None
    db.commit()

    state = run_workflow(chunks, use_llm=settings.ai_enabled, report=report)
    report(85, "Saving requirements")
    save_results(db, document, state["found"], state["conflicts"])
    report(90, "Updating chat search")
    notes = list(state["notes"]) + [index_chunks(document, chunks)]
    report(95, "Updating the knowledge graph")
    notes.append(sync_graph(db, db.get(models.Project, document.project_id)))

    document.status = "analyzed"
    db.commit()
    method = "llm" if any(item.method == "llm" for item in state["found"]) else "rules"
    return AnalysisSummary(len(state["found"]), len(state["conflicts"]), method, [n for n in notes if n])

