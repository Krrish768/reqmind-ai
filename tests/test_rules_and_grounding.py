"""Text rules, grounding checks and requirement codes."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app import models
from backend.app.agents import rules
from backend.app.api.deps import next_requirement_code
from backend.app.llm import grounding
from backend.app.schemas import ChunkIn


def test_priority_follows_the_strongest_modal() -> None:
    assert rules.priority_from_text("The system shall log in users.") == "high"
    assert rules.priority_from_text("The system should send a mail.") == "medium"
    assert rules.priority_from_text("Students may save items.") == "low"
    assert rules.priority_from_text("It may and must do this.") == "high"


def test_vague_words_are_found_as_whole_words() -> None:
    assert rules.vague_words_in("The page should be user-friendly and fast.") == ["fast", "user-friendly"]
    assert rules.vague_words_in("The breakfast menu shall be shown.") == []


def test_split_sentences_removes_bullets() -> None:
    assert rules.split_sentences("- One shall work.\n2. Two must work. Three may work.") == [
        "One shall work.", "Two must work.", "Three may work."]


def test_subject_entity() -> None:
    assert rules.subject_entity("To keep it safe, a student session shall expire.") == ["student session"]
    assert rules.subject_entity("No modal verb here.") == []


def test_rules_skip_text_without_requirements() -> None:
    chunk = ChunkIn(chunk_index=0, text="1. Introduction\nStudents wait in long queues today.")
    assert rules.extract_with_rules(chunk) == []


def test_quote_check_ignores_case_spaces_and_quotes() -> None:
    text = "The system shall lock the account after 5 failed\nlogin attempts."
    assert grounding.quote_in_text("the system shall lock the account after 5 failed login attempts", text)
    assert not grounding.quote_in_text("The system shall delete the account.", text)
    assert not grounding.quote_in_text("   ", text)


def test_unsupported_numbers() -> None:
    assert grounding.unsupported_numbers("Locks after 5 tries, not 3.", "after 5 failed logins") == ["3"]
    assert grounding.unsupported_numbers("99.5% uptime", "available 99.5% of the time") == []


def test_requirement_codes_continue_after_deletes(db: Session, client: TestClient, auth: tuple[dict, int]) -> None:
    _headers, project_id = auth
    project = db.get(models.Project, project_id)
    for code in ("REQ-001", "REQ-007"):
        db.add(models.Requirement(project_id=project_id, company_id=project.company_id, code=code,
                                  title="t", description="d"))
    db.commit()
    assert next_requirement_code(db, project_id) == "REQ-008"
