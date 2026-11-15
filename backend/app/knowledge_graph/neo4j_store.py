"""Copy a project graph into Neo4j and read it back.

Every node has the label ReqmindNode, a type label (Document, Requirement,
Entity) and the project and company ids, so projects never mix.

Example:
    python -m backend.app.knowledge_graph.neo4j_store
"""
import json
from functools import lru_cache

from neo4j import Driver, GraphDatabase
from neo4j import Session as Neo4jSession
from neo4j.exceptions import Neo4jError, ServiceUnavailable

from backend.app.config import settings
from backend.app.schemas import GraphEdge, GraphNode, GraphResponse

# What a Neo4j call can raise when the server is down or the query fails
NEO4J_ERRORS = (Neo4jError, ServiceUnavailable, OSError)
TYPE_LABELS = {"document": "Document", "requirement": "Requirement", "entity": "Entity"}
EDGE_TYPES = ["SOURCE_OF", "MENTIONS", "CONFLICTS_WITH"]

DELETE_PROJECT = "MATCH (n:ReqmindNode {project_id: $project_id}) DETACH DELETE n"
CREATE_NODES = """
UNWIND $nodes AS node
CREATE (n:ReqmindNode:{label} {{key: node.key, label: node.label, type: node.type, data: node.data,
                               project_id: $project_id, company_id: $company_id}})
"""
CREATE_EDGES = """
UNWIND $edges AS edge
MATCH (a:ReqmindNode {{key: edge.source, project_id: $project_id}})
MATCH (b:ReqmindNode {{key: edge.target, project_id: $project_id}})
CREATE (a)-[:{edge_type}]->(b)
"""
READ_NODES = """
MATCH (n:ReqmindNode {project_id: $project_id, company_id: $company_id})
RETURN n.key AS key, n.label AS label, n.type AS type, n.data AS data
"""
READ_EDGES = """
MATCH (a:ReqmindNode {project_id: $project_id})-[r]->(b:ReqmindNode {project_id: $project_id})
RETURN a.key AS source, b.key AS target, type(r) AS type
"""


@lru_cache(maxsize=1)
def get_driver() -> Driver:
    """One shared Neo4j driver."""
    return GraphDatabase.driver(settings.neo4j.uri, auth=(settings.neo4j.user, settings.neo4j.password),
                                connection_timeout=5)


def _create_nodes(session: Neo4jSession, nodes: list[GraphNode], project_id: int, company_id: int) -> None:
    """Create nodes, one query per type label (labels cannot be parameters)."""
    for node_type, label in TYPE_LABELS.items():
        rows = [{"key": node.id, "label": node.label, "type": node.type, "data": json.dumps(node.data)}
                for node in nodes if node.type == node_type]
        if rows:
            session.run(CREATE_NODES.format(label=label), nodes=rows, project_id=project_id, company_id=company_id)


def _create_edges(session: Neo4jSession, edges: list[GraphEdge], project_id: int) -> None:
    """Create edges, one query per relationship type."""
    for edge_type in EDGE_TYPES:
        rows = [{"source": edge.source, "target": edge.target} for edge in edges if edge.type == edge_type]
        if rows:
            session.run(CREATE_EDGES.format(edge_type=edge_type), edges=rows, project_id=project_id)


def sync_project(project_id: int, company_id: int, nodes: list[GraphNode], edges: list[GraphEdge]) -> None:
    """Replace the project's graph in Neo4j with these nodes and edges."""
    with get_driver().session() as session:
        session.run(DELETE_PROJECT, project_id=project_id)
        _create_nodes(session, nodes, project_id, company_id)
        _create_edges(session, edges, project_id)


def read_project(project_id: int, company_id: int) -> GraphResponse:
    """Read the project's graph from Neo4j."""
    with get_driver().session() as session:
        node_rows = session.run(READ_NODES, project_id=project_id, company_id=company_id).data()
        edge_rows = session.run(READ_EDGES, project_id=project_id).data()
    nodes = [GraphNode(id=row["key"], label=row["label"], type=row["type"], data=json.loads(row["data"] or "{}"))
             for row in node_rows]
    edges = [GraphEdge(**row) for row in edge_rows]
    return GraphResponse(nodes=nodes, edges=edges, source="neo4j")


if __name__ == "__main__":
    get_driver().verify_connectivity()
    print(f"Neo4j at {settings.neo4j.uri} is reachable")
