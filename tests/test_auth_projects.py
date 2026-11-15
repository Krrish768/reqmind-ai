"""Signup, login, projects and company isolation."""
from fastapi.testclient import TestClient

from tests.conftest import create_project, signup_and_login


def test_health(client: TestClient) -> None:
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_signup_login_and_me(client: TestClient) -> None:
    headers = signup_and_login(client, "a@example.com", "Acme")
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["email"] == "a@example.com"


def test_duplicate_email_is_rejected(client: TestClient) -> None:
    signup_and_login(client, "a@example.com", "Acme")
    response = client.post("/api/auth/signup",
                           json={"email": "a@example.com", "password": "secret123", "company_name": "Acme"})
    assert response.status_code == 400


def test_wrong_password(client: TestClient) -> None:
    signup_and_login(client, "a@example.com", "Acme")
    response = client.post("/api/auth/login", json={"email": "a@example.com", "password": "wrong-one"})
    assert response.status_code == 401


def test_bad_token(client: TestClient) -> None:
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer nonsense"}).status_code == 401


def test_projects_are_limited_to_the_company(client: TestClient) -> None:
    acme = signup_and_login(client, "a@example.com", "Acme")
    other = signup_and_login(client, "b@example.com", "Other Co")
    project_id = create_project(client, acme, "Canteen")

    assert [p["name"] for p in client.get("/api/projects", headers=acme).json()] == ["Canteen"]
    assert client.get("/api/projects", headers=other).json() == []
    assert client.get(f"/api/projects/{project_id}", headers=other).status_code == 404


def test_same_company_users_share_projects(client: TestClient) -> None:
    first = signup_and_login(client, "a@example.com", "Acme")
    second = signup_and_login(client, "c@example.com", "Acme")
    project_id = create_project(client, first)
    assert client.get(f"/api/projects/{project_id}", headers=second).status_code == 200
