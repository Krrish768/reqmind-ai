"""Build the project graph (documents, requirements, entities) from Postgres.

Postgres is the source of truth. Neo4j gets a copy of the same nodes and edges,
and this builder is also the fallback when Neo4j is off or down.
"""
from sqlalchemy.orm import Session

from backend.app import models
from backend.app.schemas import GraphEdge, GraphNode, GraphResponse


def _document_nodes(db: Session, project: models.Project) -> list[GraphNode]:
    """One node per document of the project."""
    documents = db.query(models.Document).filter(models.Document.project_id == project.id).all()
    return [GraphNode(id=f"doc:{document.id}", label=document.filename, type="document",
                      data={"status": document.status}) for document in documents]


def _requirement_node(requirement: models.Requirement) -> GraphNode:
    """Node for one requirement."""
    return GraphNode(
        id=f"req:{requirement.id}",
        label=f"{requirement.code} {requirement.title}",
        type="requirement",
        data={"priority": requirement.priority, "type": requirement.type, "status": requirement.status,
              "is_ambiguous": bool(requirement.is_ambiguous)},
    )


def _conflict_edges(db: Session, project: models.Project) -> list[GraphEdge]:
    """CONFLICTS_WITH edges between requirements."""
    conflicts = db.query(models.RequirementConflict).filter(models.RequirementConflict.project_id == project.id)
    return [GraphEdge(source=f"req:{conflict.requirement_a_id}", target=f"req:{conflict.requirement_b_id}",
                      type="CONFLICTS_WITH") for conflict in conflicts]


def graph_elements(db: Session, project: models.Project) -> tuple[list[GraphNode], list[GraphEdge]]:
    """All nodes and edges of the project.

    Returns:
        Nodes (documents, requirements, entities) and edges
        (SOURCE_OF, MENTIONS, CONFLICTS_WITH).
    """
    nodes = _document_nodes(db, project)
    edges: list[GraphEdge] = []
    entity_names: set[str] = set()
    requirements = db.query(models.Requirement).filter(models.Requirement.project_id == project.id).all()
    for requirement in requirements:
        nodes.append(_requirement_node(requirement))
        if requirement.document_id:
            edges.append(GraphEdge(source=f"doc:{requirement.document_id}", target=f"req:{requirement.id}",
                                   type="SOURCE_OF"))
        for entity in requirement.entities or []:
            entity_names.add(entity)
            edges.append(GraphEdge(source=f"req:{requirement.id}", target=f"ent:{entity}", type="MENTIONS"))
    nodes.extend(GraphNode(id=f"ent:{name}", label=name, type="entity") for name in sorted(entity_names))
    edges.extend(_conflict_edges(db, project))
    return nodes, edges


def build_graph(db: Session, project: models.Project) -> GraphResponse:
    """The project graph straight from Postgres."""
    nodes, edges = graph_elements(db, project)
    return GraphResponse(nodes=nodes, edges=edges, source="database")
