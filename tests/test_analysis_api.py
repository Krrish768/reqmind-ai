"""Analysis endpoints, jobs, graph and chat through the API."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app import models
from tests.conftest import seed_document, signup_and_login


def analyze(client: TestClient, headers: dict, project_id: int, document_id: int) -> dict:
    """Start an analysis (runs in the background of the test server) and return the finished job."""
    job = client.post(f"/api/projects/{project_id}/documents/{document_id}/analyze", headers=headers).json()
    return client.get(f"/api/jobs/{job['id']}", headers=headers).json()


def test_analysis_without_ai(client: TestClient, db: Session, auth: tuple[dict, int]) -> None:
    headers, project_id = auth
    document_id = seed_document(db, project_id)
    job = analyze(client, headers, project_id, document_id)

    assert job["status"] == "done", job["message"]
    assert job["progress"] == 100
    assert "18 requirements and 2 conflicts (rules)" in job["message"]
    assert db.get(models.Document, document_id).status == "analyzed"
    assert len(client.get(f"/api/projects/{project_id}/conflicts", headers=headers).json()) == 2


def test_analysing_again_replaces_the_old_results(client: TestClient, db: Session, auth: tuple[dict, int]) -> None:
    headers, project_id = auth
    document_id = seed_document(db, project_id)
    analyze(client, headers, project_id, document_id)
    analyze(client, headers, project_id, document_id)

    codes = [code for (code,) in db.query(models.Requirement.code).filter(models.Requirement.project_id == project_id)]
    assert len(codes) == 18
    assert len(set(codes)) == 18
    assert len(client.get(f"/api/projects/{project_id}/jobs", headers=headers).json()) == 2


def test_user_requirements_survive_a_new_analysis(client: TestClient, db: Session, auth: tuple[dict, int]) -> None:
    headers, project_id = auth
    document_id = seed_document(db, project_id)
    project = db.get(models.Project, project_id)
    db.add(models.Requirement(project_id=project_id, company_id=project.company_id, document_id=document_id,
                              code="REQ-001", title="Manual", description="Added by hand", created_by="user"))
    db.commit()
    analyze(client, headers, project_id, document_id)
    assert db.query(models.Requirement).filter(models.Requirement.created_by == "user").count() == 1


def test_unparsed_document_is_refused(client: TestClient, db: Session, auth: tuple[dict, int]) -> None:
    headers, project_id = auth
    document_id = seed_document(db, project_id, chunks=[], status="uploaded")
    response = client.post(f"/api/projects/{project_id}/documents/{document_id}/analyze", headers=headers)
    assert response.status_code == 409


def test_other_company_cannot_analyze_or_read(client: TestClient, db: Session, auth: tuple[dict, int]) -> None:
    headers, project_id = auth
    document_id = seed_document(db, project_id)
    job = analyze(client, headers, project_id, document_id)
    other = signup_and_login(client, "x@example.com", "Other Co")

    assert client.post(f"/api/projects/{project_id}/documents/{document_id}/analyze", headers=other).status_code == 404
    assert client.get(f"/api/jobs/{job['id']}", headers=other).status_code == 404
    assert client.get(f"/api/projects/{project_id}/graph", headers=other).status_code == 404
    assert client.post(f"/api/projects/{project_id}/chat", json={"question": "x"}, headers=other).status_code == 404


def test_analysis_with_llm(client: TestClient, db: Session, auth: tuple[dict, int], fake_llm: None) -> None:
    headers, project_id = auth
    job = analyze(client, headers, project_id, seed_document(db, project_id))
    assert job["status"] == "done", job["message"]
    assert "(llm)" in job["message"]


def test_analysis_when_ollama_is_down(client: TestClient, db: Session, auth: tuple[dict, int], llm_down: None) -> None:
    headers, project_id = auth
    job = analyze(client, headers, project_id, seed_document(db, project_id))
    assert job["status"] == "done"
    assert "(rules)" in job["message"]
    assert "not reachable" in job["message"]


def test_graph_from_database(client: TestClient, db: Session, auth: tuple[dict, int]) -> None:
    headers, project_id = auth
    analyze(client, headers, project_id, seed_document(db, project_id))
    graph = client.get(f"/api/projects/{project_id}/graph", headers=headers).json()

    types = {node["type"] for node in graph["nodes"]}
    edge_types = {edge["type"] for edge in graph["edges"]}
    node_ids = {node["id"] for node in graph["nodes"]}
    assert graph["source"] == "database"
    assert types == {"document", "requirement", "entity"}
    assert edge_types == {"SOURCE_OF", "MENTIONS", "CONFLICTS_WITH"}
    assert all(edge["source"] in node_ids and edge["target"] in node_ids for edge in graph["edges"])


def test_chat_without_ai_lists_passages(client: TestClient, db: Session, auth: tuple[dict, int]) -> None:
    headers, project_id = auth
    seed_document(db, project_id)
    answer = client.post(f"/api/projects/{project_id}/chat", json={"question": "When does a session expire?"},
                         headers=headers).json()
    assert answer["method"] == "template"
    assert "expire" in answer["sources"][0]["text"]


def test_chat_with_llm_uses_the_vector_index(client: TestClient, db: Session, auth: tuple[dict, int],
                                             fake_llm: None) -> None:
    headers, project_id = auth
    analyze(client, headers, project_id, seed_document(db, project_id))
    answer = client.post(f"/api/projects/{project_id}/chat", json={"question": "How do students pay?"},
                         headers=headers).json()
    assert answer["method"] == "llm"
    assert len(answer["sources"]) == 1
    assert answer["sources"][0]["filename"] == "canteen_srs.pdf"


def test_chat_with_no_documents(client: TestClient, auth: tuple[dict, int]) -> None:
    headers, project_id = auth
    answer = client.post(f"/api/projects/{project_id}/chat", json={"question": "Anything?"}, headers=headers).json()
    assert answer["sources"] == []
