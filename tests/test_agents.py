"""LLM extraction with grounding, conflicts and the workflow fallbacks."""
import pytest

from backend.app.agents import conflicts, extraction
from backend.app.agents.workflow import LLM_DOWN_NOTE, run_workflow
from backend.app.llm import client as llm
from backend.app.schemas import (
    ChunkIn,
    LlmConflictVerdict,
    LlmExtraction,
    LlmRequirement,
)
from tests.conftest import SAMPLE_CHUNKS

CHUNK = ChunkIn(chunk_index=0, chunk_id=7, text="The system shall lock an account after 5 failed login attempts.")
SAMPLE = [ChunkIn(**chunk) for chunk in SAMPLE_CHUNKS]


def llm_item(quote: str, entities: list[str]) -> LlmRequirement:
    return LlmRequirement(title="Lock account", description="Lock after 5 failures.", type="functional",
                          category="security", source_quote=quote, entities=entities, is_ambiguous=False,
                          ambiguity_note=None)


def no_report(_percent: int, _message: str) -> None:
    pass


def test_grounded_item_is_kept_and_priority_comes_from_rules(fake_llm: None) -> None:
    found = extraction.extract_with_llm(CHUNK)
    assert len(found) == 1
    assert found[0].priority == "high"
    assert found[0].chunk_id == 7
    assert found[0].method == "llm"


def test_retry_fixes_an_invented_quote(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = [
        LlmExtraction(requirements=[llm_item("The system shall delete accounts.", ["account"])]),
        LlmExtraction(requirements=[llm_item(CHUNK.text, ["account", "spaceship"])]),
    ]
    prompts_seen = []

    def scripted(_system: str, user_prompt: str, _schema: type) -> LlmExtraction:
        prompts_seen.append(user_prompt)
        return answers.pop(0)

    monkeypatch.setattr(llm, "chat_json", scripted)
    found = extraction.extract_with_llm(CHUNK)
    assert "source_quote is not in the text" in prompts_seen[1]
    assert len(found) == 1
    assert found[0].entities == ["account"]  # the invented entity is dropped


def test_items_still_invented_after_retry_are_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    invented = LlmExtraction(requirements=[llm_item("The system shall fly.", [])])
    monkeypatch.setattr(llm, "chat_json", lambda *_args: invented)
    assert extraction.extract_with_llm(CHUNK) == []


def test_rules_find_the_two_sample_conflicts() -> None:
    state = run_workflow(SAMPLE, use_llm=False, report=no_report)
    pairs = {(state["found"][c.index_a].source_quote[:20], state["found"][c.index_b].source_quote[:20])
             for c in state["conflicts"]}
    assert len(state["conflicts"]) == 2
    assert ("A student session sh", "To keep the app secu") in pairs


def test_ungrounded_llm_reason_falls_back_to_the_template(monkeypatch: pytest.MonkeyPatch) -> None:
    bad = LlmConflictVerdict(is_conflict=True, reason="One says 15 and the other says 45 minutes.")
    monkeypatch.setattr(llm, "chat_json", lambda *_args: bad)
    state = run_workflow(SAMPLE, use_llm=False, report=no_report)
    found_conflicts = conflicts.detect_conflicts(state["found"], None, use_llm=True)
    assert all("45" not in conflict.reason for conflict in found_conflicts)
    assert len(found_conflicts) == 2


def test_llm_says_no_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm, "chat_json", lambda *_args: LlmConflictVerdict(is_conflict=False, reason="Fine."))
    state = run_workflow(SAMPLE, use_llm=False, report=no_report)
    assert conflicts.detect_conflicts(state["found"], None, use_llm=True) == []


def test_workflow_with_llm(fake_llm: None) -> None:
    state = run_workflow(SAMPLE, use_llm=True, report=no_report)
    assert len(state["found"]) == 18
    assert all(item.method == "llm" for item in state["found"])
    assert state["vectors"] is not None
    assert state["notes"] == []


def test_workflow_switches_to_rules_when_ollama_is_down(llm_down: None) -> None:
    state = run_workflow(SAMPLE, use_llm=True, report=no_report)
    assert len(state["found"]) == 18
    assert all(item.method == "rules" for item in state["found"])
    assert state["notes"] == [LLM_DOWN_NOTE]
    assert len(state["conflicts"]) == 2


def test_progress_is_reported_in_order() -> None:
    seen = []
    run_workflow(SAMPLE, use_llm=False, report=lambda percent, _message: seen.append(percent))
    assert seen == sorted(seen)
    assert seen[0] >= 5


def test_section_heading_is_not_used_as_title() -> None:
    chunk_text = "4. Payments\n- The system shall accept payments through UPI."
    quote = "The system shall accept payments through UPI."
    assert extraction.checked_title("Payments", quote, chunk_text) == "Accept payments through UPI"
    assert extraction.checked_title("6. Quality", quote, chunk_text) == "Accept payments through UPI"
    assert extraction.checked_title("UPI payments", quote, chunk_text) == "UPI payments"
    long_quote = "The system shall accept payments through UPI using the payment gateway for every order."
    expected = "Accept payments through UPI using the payment gateway"
    assert extraction.checked_title(long_quote, long_quote, chunk_text) == expected
