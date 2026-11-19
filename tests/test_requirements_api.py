"""Add, list, filter, edit and delete requirements, and export them."""
import io

import docx
from fastapi.testclient import TestClient
from pypdf import PdfReader
from sqlalchemy.orm import Session

from backend.app.api.export import file_name
from tests.conftest import seed_document, signup_and_login


def add(client: TestClient, headers: dict, project_id: int, title: str, **fields: object) -> dict:
    """Create one requirement by hand."""
    body = {"title": title, "description": f"{title} description.", **fields}
    return client.post(f"/api/projects/{project_id}/requirements", json=body, headers=headers).json()


def test_add_and_list_in_code_order(client: TestClient, auth: tuple[dict, int]) -> None:
    headers, project_id = auth
    first = add(client, headers, project_id, "Login")
    second = add(client, headers, project_id, "Logout", type="non_functional", priority="low")
    assert (first["code"], second["code"]) == ("REQ-001", "REQ-002")
    assert first["created_by"] == "user"
    listed = client.get(f"/api/projects/{project_id}/requirements", headers=headers).json()
    assert [item["code"] for item in listed] == ["REQ-001", "REQ-002"]


def test_filters(client: TestClient, auth: tuple[dict, int]) -> None:
    headers, project_id = auth
    add(client, headers, project_id, "Login")
    add(client, headers, project_id, "Fast", type="non_functional")
    url = f"/api/projects/{project_id}/requirements"
    assert [r["title"] for r in client.get(url, params={"type": "non_functional"}, headers=headers).json()] == ["Fast"]
    assert client.get(url, params={"status": "approved"}, headers=headers).json() == []
    assert client.get(url, params={"type": "wrong"}, headers=headers).status_code == 422


def test_edit_changes_only_sent_fields(client: TestClient, auth: tuple[dict, int]) -> None:
    headers, project_id = auth
    item = add(client, headers, project_id, "Login", priority="high")
    url = f"/api/projects/{project_id}/requirements/{item['id']}"
    edited = client.patch(url, json={"status": "approved", "entities": ["user"]}, headers=headers).json()
    assert (edited["status"], edited["priority"], edited["entities"]) == ("approved", "high", ["user"])
    assert client.patch(url, json={"priority": "urgent"}, headers=headers).status_code == 422


def test_delete_removes_its_conflicts(client: TestClient, db: Session, auth: tuple[dict, int]) -> None:
    headers, project_id = auth
    document_id = seed_document(db, project_id)
    client.post(f"/api/projects/{project_id}/documents/{document_id}/analyze", headers=headers)
    conflict = client.get(f"/api/projects/{project_id}/conflicts", headers=headers).json()[0]
    url = f"/api/projects/{project_id}/requirements/{conflict['requirement_a_id']}"
    assert client.delete(url, headers=headers).status_code == 204
    assert len(client.get(f"/api/projects/{project_id}/conflicts", headers=headers).json()) == 1


def test_other_company_cannot_touch_requirements(client: TestClient, auth: tuple[dict, int]) -> None:
    headers, project_id = auth
    item = add(client, headers, project_id, "Login")
    other = signup_and_login(client, "x@example.com", "Other Co")
    url = f"/api/projects/{project_id}/requirements/{item['id']}"
    assert client.patch(url, json={"title": "x"}, headers=other).status_code == 404
    assert client.delete(url, headers=other).status_code == 404
    assert client.get(f"/api/projects/{project_id}/export", headers=other).status_code == 404


def analyzed_project(client: TestClient, db: Session, auth: tuple[dict, int]) -> tuple[dict, int]:
    """A project with the sample document analyzed (18 requirements, 2 conflicts)."""
    headers, project_id = auth
    document_id = seed_document(db, project_id)
    client.post(f"/api/projects/{project_id}/documents/{document_id}/analyze", headers=headers)
    return headers, project_id


def test_export_markdown(client: TestClient, db: Session, auth: tuple[dict, int]) -> None:
    headers, project_id = analyzed_project(client, db, auth)
    response = client.get(f"/api/projects/{project_id}/export", params={"format": "md"}, headers=headers)
    text = response.text
    assert response.headers["content-type"].startswith("text/markdown")
    assert "| Requirements | 18 |" in text
    assert "| Conflicts | 2 |" in text
    assert "## Non-functional" in text
    assert 'filename="canteen_requirements.md"' in response.headers["content-disposition"]


def test_export_docx_and_pdf_open(client: TestClient, db: Session, auth: tuple[dict, int]) -> None:
    headers, project_id = analyzed_project(client, db, auth)
    url = f"/api/projects/{project_id}/export"
    word = docx.Document(io.BytesIO(client.get(url, params={"format": "docx"}, headers=headers).content))
    assert any("REQ-001" in paragraph.text for paragraph in word.paragraphs)
    pdf = PdfReader(io.BytesIO(client.get(url, params={"format": "pdf"}, headers=headers).content))
    assert "Conflicts" in "".join(page.extract_text() for page in pdf.pages)


def test_export_empty_project(client: TestClient, auth: tuple[dict, int]) -> None:
    headers, project_id = auth
    text = client.get(f"/api/projects/{project_id}/export", headers=headers).text
    assert "No conflicts found." in text


def test_file_name() -> None:
    assert file_name("Canteen App (v2)!", "pdf") == "canteen_app_v2_requirements.pdf"
    assert file_name("***", "md") == "project_requirements.md"
