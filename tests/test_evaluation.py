"""Scoring of the evaluation, and the text rules on the labelled documents."""
from backend.app.evaluation import runner, scoring
from backend.app.evaluation.dataset import EvalLine, load_documents
from backend.app.schemas import FoundConflict, FoundRequirement


def found(quote: str) -> FoundRequirement:
    return FoundRequirement(title="t", description=quote, type="functional", category=None, priority="medium",
                            source_quote=quote, entities=[], is_ambiguous=False, ambiguity_note=None,
                            chunk_index=0, chunk_id=None, method="rules")


def test_closest_label_wins() -> None:
    labels = [EvalLine("- Patients can cancel up to 2 hours before it starts.", "H3"),
              EvalLine("- A patient may cancel up to 6 hours before it starts.", "H5")]
    items = [found("A patient may cancel up to 6 hours before it starts.")]
    assert scoring.match_requirements(items, labels) == {0: "H5"}


def test_unrelated_sentence_is_not_matched() -> None:
    labels = [EvalLine("- The system shall send an SMS reminder.", "H4")]
    assert scoring.match_requirements([found("Most patients will use the app on their phones.")], labels) == {}


def test_lookalike_reported_counts_as_false_alarm() -> None:
    document = next(doc for doc in load_documents() if doc.name == "library")
    items = [found("A student shall reserve at most 3 books at the same time."),
             found("A student may reserve up to 5 books at one time during exam weeks.")]
    matches = scoring.match_requirements(items, document.requirements)
    counts = scoring.conflict_counts([FoundConflict(index_a=0, index_b=1, reason="x")], document, matches)
    assert counts["conflicts_extra"] == 1
    assert counts["lookalikes_reported"] == 1


def test_rules_on_the_labelled_documents() -> None:
    per_document = [runner.evaluate_document(document, use_llm=False) for document in load_documents()]
    total = runner.totals(per_document)
    assert (total["labelled"], total["found"], total["correct"]) == (65, 62, 60)
    assert (total["conflicts_labelled"], total["conflicts_correct"], total["lookalikes_reported"]) == (5, 4, 3)
    assert total["vague_recall"] == 1.0
