"""Find pairs of requirements that contradict each other.

Candidate pairs come from measured signals: embedding similarity, shared
entities and different numbers for the same unit. The LLM only judges the
candidates and writes the reason, and the reason is checked against the two
requirements. Without the LLM, only clear number clashes are reported.

Example:
    python -m backend.app.agents.conflicts
"""
import re
from dataclasses import dataclass

import numpy as np

from backend.app.config import settings
from backend.app.llm import client as llm
from backend.app.llm import grounding, prompts
from backend.app.schemas import FoundConflict, FoundRequirement, LlmConflictVerdict

VALUE_WITH_UNIT = re.compile(r"(\d+(?:\.\d+)?)\s*(%|[a-zA-Z]+)")
STOP_WORDS = {"shall", "must", "should", "will", "with", "that", "this", "from", "have", "their", "they", "when",
              "into", "after", "before", "each", "every", "user", "users", "system"}
MIN_WORD_OVERLAP = 0.3


@dataclass
class Candidate:
    index_a: int
    index_b: int
    similarity: float
    number_clash: str | None  # template reason when the numbers differ


def values_by_unit(text: str) -> dict[str, set[str]]:
    """{"minutes": {"15"}} for "after 15 minutes"."""
    values: dict[str, set[str]] = {}
    for value, unit in VALUE_WITH_UNIT.findall(text):
        values.setdefault(unit.lower().rstrip("s"), set()).add(value)
    return values


def number_clash(a: FoundRequirement, b: FoundRequirement) -> str | None:
    """A template reason if both use the same unit with different values."""
    values_a = values_by_unit(a.source_quote)
    values_b = values_by_unit(b.source_quote)
    for unit in sorted(values_a.keys() & values_b.keys()):
        if values_a[unit] != values_b[unit]:
            first = ", ".join(sorted(values_a[unit]))
            second = ", ".join(sorted(values_b[unit]))
            return f'"{a.title}" uses {first} {unit}(s), but "{b.title}" uses {second} {unit}(s).'
    return None


def word_overlap(a: str, b: str) -> float:
    """Jaccard overlap of the longer content words of two sentences."""
    words_a = {word for word in re.findall(r"[a-z]{4,}", a.lower()) if word not in STOP_WORDS}
    words_b = {word for word in re.findall(r"[a-z]{4,}", b.lower()) if word not in STOP_WORDS}
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def similarity_matrix(vectors: list[list[float]]) -> np.ndarray:
    """Cosine similarity between every pair of vectors."""
    matrix = np.array(vectors, dtype=float)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    matrix = matrix / np.where(norms == 0, 1, norms)
    return matrix @ matrix.T


def _is_candidate(a: FoundRequirement, b: FoundRequirement, similarity: float, clash: str | None) -> bool:
    """Close in meaning, or the same topic with different numbers."""
    if similarity >= settings.analysis.conflict_similarity:
        return True
    shared_entity = bool(set(a.entities) & set(b.entities))
    same_topic = shared_entity or word_overlap(a.description, b.description) >= MIN_WORD_OVERLAP
    return clash is not None and same_topic


def find_candidates(found: list[FoundRequirement], vectors: list[list[float]] | None) -> list[Candidate]:
    """Candidate pairs, number clashes first, then by similarity."""
    similarities = similarity_matrix(vectors) if vectors else None
    candidates = []
    for i in range(len(found)):
        for j in range(i + 1, len(found)):
            similarity = float(similarities[i, j]) if similarities is not None else 0.0
            clash = number_clash(found[i], found[j])
            if _is_candidate(found[i], found[j], similarity, clash):
                candidates.append(Candidate(i, j, similarity, clash))
    candidates.sort(key=lambda candidate: (candidate.number_clash is None, -candidate.similarity))
    return candidates[: settings.analysis.max_conflict_pairs]


def _pair_prompt(a: FoundRequirement, b: FoundRequirement, errors: list[str]) -> str:
    """User prompt with both requirements and, on retry, the errors."""
    text = f"Requirement A: {a.source_quote}\nRequirement B: {b.source_quote}"
    if errors:
        text += "\n\n" + prompts.CONFLICT_RETRY.format(errors="\n".join(errors))
    return text


def judge_with_llm(a: FoundRequirement, b: FoundRequirement) -> LlmConflictVerdict | None:
    """Ask the LLM; return its verdict only if the reason is grounded.

    Raises:
        LlmUnavailable: Ollama is down.
    """
    facts = f"{a.source_quote} {b.source_quote}"
    errors: list[str] = []
    for _attempt in range(2):
        try:
            verdict = llm.chat_json(prompts.CONFLICT_SYSTEM, _pair_prompt(a, b, errors), LlmConflictVerdict)
        except llm.LlmBadOutput as error:
            errors = [str(error)]
            continue
        missing = grounding.unsupported_numbers(verdict.reason, facts)
        if not verdict.is_conflict or not missing:
            return verdict
        errors = [f"These numbers are not in the requirements: {missing}"]
    return None


def detect_conflicts(found: list[FoundRequirement], vectors: list[list[float]] | None,
                     use_llm: bool) -> list[FoundConflict]:
    """Judge each candidate pair and return the conflicts.

    Raises:
        LlmUnavailable: Ollama went down; the caller can retry with use_llm=False.
    """
    conflicts = []
    for candidate in find_candidates(found, vectors):
        a, b = found[candidate.index_a], found[candidate.index_b]
        reason = candidate.number_clash
        if use_llm:
            verdict = judge_with_llm(a, b)
            if verdict is not None:
                reason = verdict.reason if verdict.is_conflict else None
        if reason:
            conflicts.append(FoundConflict(index_a=candidate.index_a, index_b=candidate.index_b, reason=reason))
    return conflicts


if __name__ == "__main__":
    from backend.app.agents.rules import extract_with_rules
    from backend.app.schemas import ChunkIn

    text = "The session shall expire after 15 minutes.\nThe session shall expire after 30 minutes of no activity."
    demo = extract_with_rules(ChunkIn(chunk_index=0, text=text))
    for conflict in detect_conflicts(demo, None, use_llm=False):
        print(conflict.reason)
