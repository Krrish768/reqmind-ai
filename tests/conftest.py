"""Shared test setup: a throwaway SQLite database, an API client and a fake LLM.

The tests never need Ollama, Qdrant, Neo4j or Redis. Run from the repo root:
    python -m pytest -q
"""
import hashlib
import json
import os
import re
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

TEST_DB = Path(tempfile.gettempdir()) / "reqmind_test.db"
os.environ["APP_CONFIG"] = "cpu_laptop"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-that-is-long-enough-123456"

from fastapi.testclient import TestClient  # noqa: E402  (env must be set before the app is imported)
from sqlalchemy.orm import Session  # noqa: E402

from backend.app import models  # noqa: E402
from backend.app.agents import rules  # noqa: E402
from backend.app.config import REPO_ROOT, settings  # noqa: E402
from backend.app.database import Base, SessionLocal, engine  # noqa: E402
from backend.app.llm import client as llm  # noqa: E402
from backend.app.main import app  # noqa: E402
from backend.app.rag import vector_store  # noqa: E402
from backend.app.schemas import (  # noqa: E402
    LlmChatAnswer,
    LlmConflictVerdict,
    LlmExtraction,
    LlmRequirement,
)

SAMPLE_CHUNKS = json.loads((REPO_ROOT / "samples" / "chunks.json").read_text())
EMBED_SIZE = 64


@pytest.fixture(autouse=True)
def fresh_database() -> None:
    """Empty tables before every test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


@pytest.fixture
def client() -> Iterator[TestClient]:
    """API client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def db() -> Iterator[Session]:
    """A database session for setting up and checking rows."""
    session = SessionLocal()
    yield session
    session.close()


def signup_and_login(client: TestClient, email: str, company: str) -> dict:
    """Create a user and return the auth header."""
    client.post("/api/auth/signup", json={"email": email, "password": "secret123", "company_name": company})
    token = client.post("/api/auth/login", json={"email": email, "password": "secret123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_project(client: TestClient, headers: dict, name: str = "Canteen") -> int:
    """Create a project and return its id."""
    return client.post("/api/projects", json={"name": name}, headers=headers).json()["id"]


def seed_document(db: Session, project_id: int, chunks: list[dict] = SAMPLE_CHUNKS, status: str = "parsed") -> int:
    """Insert a parsed document with chunks, the way the upload step saves it."""
    project = db.get(models.Project, project_id)
    document = models.Document(project_id=project_id, company_id=project.company_id, filename="canteen_srs.pdf",
                               content_type="application/pdf", storage_key=f"test/{project_id}.pdf",
                               size_bytes=1000, status=status)
    db.add(document)
    db.flush()
    for chunk in chunks:
        db.add(models.DocumentChunk(document_id=document.id, chunk_index=chunk["chunk_index"],
                                    text=chunk["text"], page=chunk["page"]))
    db.commit()
    return document.id


@pytest.fixture
def auth(client: TestClient) -> tuple[dict, int]:
    """Logged-in user with one project: (headers, project_id)."""
    headers = signup_and_login(client, "krrish@example.com", "Acme")
    return headers, create_project(client, headers)


# ---------- fake LLM ----------
def fake_embedding(text: str) -> list[float]:
    """Deterministic bag-of-words vector, so similar texts get similar vectors."""
    vector = [0.0] * EMBED_SIZE
    for word in re.findall(r"[a-z]+", text.lower()):
        vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % EMBED_SIZE] += 1.0
    return vector


def fake_extraction(user_prompt: str) -> LlmExtraction:
    """Grounded requirements built from the text rules."""
    text = user_prompt.split("Text:\n", 1)[1].split("\n\nYour last answer", 1)[0]
    items = []
    for sentence in rules.split_sentences(text):
        if rules.strongest_modal(sentence):
            items.append(LlmRequirement(
                title=rules.make_title(sentence), description=sentence, type=rules.type_from_text(sentence),
                category=rules.category_from_text(sentence), source_quote=sentence,
                entities=rules.subject_entity(sentence), is_ambiguous=False, ambiguity_note=None))
    return LlmExtraction(requirements=items)


def fake_chat_json(system_prompt: str, user_prompt: str, schema: type) -> object:
    """Answers that always pass the grounding checks."""
    if schema is LlmExtraction:
        return fake_extraction(user_prompt)
    if schema is LlmConflictVerdict:
        return LlmConflictVerdict(is_conflict=True, reason="Both set a different limit for the same thing.")
    if schema is LlmChatAnswer:
        return LlmChatAnswer(answer="The documents describe this.", passages=["A"])
    raise AssertionError(f"unexpected schema {schema}")


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Turn AI on with a fake LLM, in-memory Qdrant and no Neo4j or Redis."""
    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(settings.qdrant, "enabled", True)
    monkeypatch.setattr(settings.qdrant, "url", ":memory:")
    monkeypatch.setattr(llm, "chat_json", fake_chat_json)
    monkeypatch.setattr(llm, "embed_texts", lambda texts, is_query=False: [fake_embedding(t) for t in texts])
    vector_store.get_qdrant.cache_clear()
    yield
    vector_store.get_qdrant.cache_clear()


@pytest.fixture
def llm_down(monkeypatch: pytest.MonkeyPatch) -> None:
    """Turn AI on, but every Ollama call fails as if the server were off."""
    def unavailable(*_args: object, **_kwargs: object) -> None:
        raise llm.LlmUnavailable("Ollama chat failed: connection refused")

    monkeypatch.setattr(settings, "ai_enabled", True)
    monkeypatch.setattr(llm, "chat_json", unavailable)
    monkeypatch.setattr(llm, "embed_texts", unavailable)
