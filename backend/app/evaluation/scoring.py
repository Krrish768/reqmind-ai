"""Compare what the analysis found with the labels.

A found requirement counts as correct when its source sentence matches a
labelled requirement sentence: one contains the other after normalizing, or
they share at least 60% of their words. The closest pairs are matched first,
and each label can be matched only once.
"""
import re

from backend.app.evaluation.dataset import EvalDocument, EvalLine
from backend.app.llm.grounding import normalize
from backend.app.schemas import FoundConflict, FoundRequirement

MIN_OVERLAP = 0.6


def _words(text: str) -> set[str]:
    """Lowercase words of 2 or more characters."""
    return set(re.findall(r"[a-z0-9%.]{2,}", text.lower()))


def overlap(found_quote: str, label_text: str) -> float:
    """1.0 if one sentence contains the other, else the share of shared words."""
    found, label = normalize(found_quote), normalize(label_text)
    if not found or not label:
        return 0.0
    if found in label or label in found:
        return 1.0
    found_words, label_words = _words(found), _words(label)
    return len(found_words & label_words) / max(len(found_words | label_words), 1)


def match_requirements(found: list[FoundRequirement], labels: list[EvalLine]) -> dict[int, str]:
    """{position in found: label id}. Best pairs first, each label and each found item used once."""
    pairs = []
    for position, item in enumerate(found):
        for label in labels:
            score = overlap(item.source_quote, label.text)
            if score >= MIN_OVERLAP:
                pairs.append((score, position, label.req_id))
    matches: dict[int, str] = {}
    used: set[str] = set()
    for _score, position, req_id in sorted(pairs, key=lambda pair: -pair[0]):
        if position not in matches and req_id not in used:
            matches[position] = req_id
            used.add(req_id)
    return matches


def ratio(part: int, whole: int) -> float | None:
    """part / whole rounded to 3 places, or None when whole is 0."""
    return round(part / whole, 3) if whole else None


def f1(precision: float | None, recall: float | None) -> float | None:
    """Harmonic mean of precision and recall."""
    if not precision or not recall:
        return 0.0 if precision is not None and recall is not None else None
    return round(2 * precision * recall / (precision + recall), 3)


def extraction_counts(found: list[FoundRequirement], document: EvalDocument,
                      matches: dict[int, str]) -> dict:
    """Correct, extra and missed requirements, and correct types."""
    by_id = {label.req_id: label for label in document.requirements}
    found_ids = set(matches.values())
    type_correct = sum(1 for position, req_id in matches.items() if found[position].type == by_id[req_id].type)
    return {
        "correct": len(matches),
        "extra": len(found) - len(matches),
        "missed": len(by_id) - len(found_ids),
        "type_correct": type_correct,
        "extra_sentences": [found[p].source_quote for p in range(len(found)) if p not in matches],
        "missed_sentences": [by_id[i].text for i in by_id if i not in found_ids],
    }


def vague_counts(found: list[FoundRequirement], document: EvalDocument, matches: dict[int, str]) -> dict:
    """Vague flags on matched requirements compared with the labels."""
    labelled = {label.req_id for label in document.requirements if label.vague}
    flagged = {req_id for position, req_id in matches.items() if found[position].is_ambiguous}
    return {"vague_correct": len(flagged & labelled), "vague_extra": len(flagged - labelled),
            "vague_missed": len(labelled - flagged)}


def conflict_counts(conflicts: list[FoundConflict], document: EvalDocument, matches: dict[int, str]) -> dict:
    """Found, falsely reported and missed conflicts; look-alikes reported by mistake."""
    real = {frozenset(pair) for pair in document.conflicts}
    lookalikes = {frozenset(pair) for pair in document.lookalikes}
    correct: set[frozenset] = set()
    extra = lookalikes_reported = 0
    for conflict in conflicts:
        first, second = matches.get(conflict.index_a), matches.get(conflict.index_b)
        pair = frozenset((first, second)) if first and second else None
        if pair in real:
            correct.add(pair)
            continue
        extra += 1
        lookalikes_reported += pair in lookalikes
    return {"conflicts_correct": len(correct), "conflicts_extra": extra, "conflicts_missed": len(real - correct),
            "lookalikes_reported": lookalikes_reported, "lookalikes_total": len(lookalikes)}
