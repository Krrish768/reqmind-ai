"""Upload, list, download and delete documents through the API, then analyze one."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app import models
from backend.app.ingestion import storage
from tests.conftest import signup_and_login
from tests.test_ingestion import make_docx, make_pdf

SRS_LINES = [
    "2. Accounts",
    "- A student session shall expire after 15 minutes of inactivity.",
    "- The system shall lock an account after 5 failed login attempts.",
    "- A student session shall expire after 30 minutes of inactivity.",
]


@pytest.fixture
def fake_storage(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Keep uploaded files in a dict instead of the S3 store."""
    files: dict[str, bytes] = {}
    monkeypatch.setattr(storage, "save_file", lambda key, data, _type: files.__setitem__(key, data))
    monkeypatch.setattr(storage, "read_file", lambda key: files[key])
    monkeypatch.setattr(storage, "delete_file", lambda key: files.pop(key, None))
    return files


def upload(client: TestClient, headers: dict, project_id: int, filename: str, data: bytes) -> dict:
    """POST one file and return the JSON answer."""
    response = client.post(f"/api/projects/{project_id}/documents", headers=headers,
                           files={"file": (filename, data)})
    return {"status_code": response.status_code, **response.json()}


def test_upload_docx_is_parsed_into_chunks(client: TestClient, auth: tuple[dict, int], fake_storage: dict) -> None:
    headers, project_id = auth
    document = upload(client, headers, project_id, "canteen.docx", make_docx(SRS_LINES))
    assert document["status"] == "parsed", document
    chunks = client.get(f"/api/projects/{project_id}/documents/{document['id']}/chunks", headers=headers).json()
    assert "15 minutes" in chunks[0]["text"]
    assert len(fake_storage) == 1


def test_upload_pdf_and_download_the_original(client: TestClient, auth: tuple[dict, int],
                                              fake_storage: dict) -> None:
    headers, project_id = auth
    data = make_pdf([SRS_LINES[:2], SRS_LINES[2:]])
    document = upload(client, headers, project_id, "canteen.pdf", data)
    chunks = client.get(f"/api/projects/{project_id}/documents/{document['id']}/chunks", headers=headers).json()
    assert [chunk["page"] for chunk in chunks] == [1, 2]
    download = client.get(f"/api/projects/{project_id}/documents/{document['id']}/file", headers=headers)
    assert download.content == data
    assert 'filename="canteen.pdf"' in download.headers["content-disposition"]


def test_file_without_text_is_saved_as_failed(client: TestClient, auth: tuple[dict, int],
                                              fake_storage: dict) -> None:
    headers, project_id = auth
    document = upload(client, headers, project_id, "scan.pdf", make_pdf([[]]))
    assert document["status"] == "failed"
    assert "could not find any text" in document["error"]


@pytest.mark.parametrize("filename, data", [("photo.png", b"abc"), ("empty.txt", b"")])
def test_bad_uploads_are_refused(client: TestClient, auth: tuple[dict, int], fake_storage: dict,
                                 filename: str, data: bytes) -> None:
    headers, project_id = auth
    assert upload(client, headers, project_id, filename, data)["status_code"] == 400
    assert fake_storage == {}


def test_storage_down_gives_503(client: TestClient, auth: tuple[dict, int], monkeypatch: pytest.MonkeyPatch) -> None:
    def down(*_args: object) -> None:
        raise OSError("connection refused")

    monkeypatch.setattr(storage, "save_file", down)
    headers, project_id = auth
    response = upload(client, headers, project_id, "a.txt", b"The system shall work.")
    assert response["status_code"] == 503
    assert "docker compose up" in response["detail"]


def test_list_and_delete_keep_requirements(client: TestClient, db: Session, auth: tuple[dict, int],
                                           fake_storage: dict) -> None:
    headers, project_id = auth
    document = upload(client, headers, project_id, "srs.txt", "\n".join(SRS_LINES).encode())
    client.post(f"/api/projects/{project_id}/documents/{document['id']}/analyze", headers=headers)
    assert len(client.get(f"/api/projects/{project_id}/documents", headers=headers).json()) == 1

    response = client.delete(f"/api/projects/{project_id}/documents/{document['id']}", headers=headers)
    assert response.status_code == 204
    assert client.get(f"/api/projects/{project_id}/documents", headers=headers).json() == []
    assert fake_storage == {}
    assert db.query(models.DocumentChunk).count() == 0
    requirements = client.get(f"/api/projects/{project_id}/requirements", headers=headers).json()
    assert len(requirements) == 3
    assert all(requirement["document_id"] is None for requirement in requirements)


def test_uploaded_file_goes_through_the_analysis(client: TestClient, auth: tuple[dict, int],
                                                 fake_storage: dict) -> None:
    headers, project_id = auth
    document = upload(client, headers, project_id, "srs.docx", make_docx(SRS_LINES))
    job = client.post(f"/api/projects/{project_id}/documents/{document['id']}/analyze", headers=headers).json()
    job = client.get(f"/api/jobs/{job['id']}", headers=headers).json()
    assert job["status"] == "done", job["message"]
    assert len(client.get(f"/api/projects/{project_id}/conflicts", headers=headers).json()) == 1


def test_other_company_cannot_see_documents(client: TestClient, auth: tuple[dict, int], fake_storage: dict) -> None:
    headers, project_id = auth
    document = upload(client, headers, project_id, "srs.txt", b"The system shall work.")
    other = signup_and_login(client, "x@example.com", "Other Co")
    assert client.get(f"/api/projects/{project_id}/documents", headers=other).status_code == 404
    assert client.get(f"/api/projects/{project_id}/documents/{document['id']}/file", headers=other).status_code == 404
    assert client.delete(f"/api/projects/{project_id}/documents/{document['id']}", headers=other).status_code == 404
