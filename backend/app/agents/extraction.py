"""Find requirements in one chunk with the LLM, and check every one against the text.

A requirement is kept only if its source quote is really in the chunk. On
problems the LLM gets one retry with the list of errors; after that only the
checked items are kept.

Example:
    python -m backend.app.agents.extraction
"""
import re

from backend.app.agents import rules
from backend.app.llm import client as llm
from backend.app.llm import grounding, prompts
from backend.app.schemas import ChunkIn, FoundRequirement, LlmExtraction, LlmRequirement

MAX_TITLE_WORDS = 10


def grounding_errors(items: list[LlmRequirement], chunk_text: str) -> list[str]:
    """One line per item whose quote or entities are not in the chunk."""
    errors = []
    for number, item in enumerate(items, start=1):
        if not grounding.quote_in_text(item.source_quote, chunk_text):
            errors.append(f"Item {number}: source_quote is not in the text: {item.source_quote!r}")
        bad_entities = [entity for entity in item.entities if not grounding.entity_in_text(entity, chunk_text)]
        if bad_entities:
            errors.append(f"Item {number}: entities not in the text: {bad_entities}")
    return errors


def _words(text: str) -> set[str]:
    """Lowercase words of 3 or more letters."""
    return set(re.findall(r"[a-z]{3,}", text.lower()))


def heading_lines(chunk_text: str) -> set[str]:
    """Normalized lines without a modal verb, like "4. Payments" -> "payments"."""
    lines = (rules.BULLET_PREFIX.sub("", line) for line in chunk_text.splitlines())
    return {grounding.normalize(line) for line in lines if line.strip() and not rules.strongest_modal(line)}


def checked_title(title: str, quote: str, chunk_text: str) -> str:
    """Keep the LLM title only if it has 2 to MAX_TITLE_WORDS words, shares a word with the quote
    and is not a heading.

    Otherwise make the title from the quote with the text rules.
    """
    clean = title.strip()
    is_heading = grounding.normalize(rules.BULLET_PREFIX.sub("", clean)) in heading_lines(chunk_text)
    if not 2 <= len(clean.split()) <= MAX_TITLE_WORDS or is_heading or not _words(clean) & _words(quote):
        return rules.make_title(quote)
    return clean


def to_found(item: LlmRequirement, chunk: ChunkIn) -> FoundRequirement:
    """Turn a checked LLM item into a FoundRequirement.

    Priority and vague words come from the text rules, not from the LLM.
    """
    vague = rules.vague_words_in(item.source_quote)
    notes = [note for note in (item.ambiguity_note if item.is_ambiguous else None, rules.vague_note(vague)) if note]
    entities = [grounding.normalize(entity) for entity in item.entities if grounding.entity_in_text(entity, chunk.text)]
    return FoundRequirement(
        title=checked_title(item.title, item.source_quote, chunk.text),
        description=item.description.strip(),
        type=item.type,
        category=item.category,
        priority=rules.priority_from_text(item.source_quote),
        source_quote=item.source_quote.strip(),
        entities=sorted(set(entities)),
        is_ambiguous=item.is_ambiguous or bool(vague),
        ambiguity_note="; ".join(notes) or None,
        chunk_index=chunk.chunk_index,
        chunk_id=chunk.chunk_id,
        method="llm",
    )


def _ask(chunk: ChunkIn, errors: list[str]) -> list[LlmRequirement]:
    """One LLM call. Adds the retry note when there were errors."""
    user_prompt = f"Text:\n{chunk.text}"
    if errors:
        user_prompt += "\n\n" + prompts.EXTRACTION_RETRY.format(errors="\n".join(errors))
    result = llm.chat_json(prompts.EXTRACTION_SYSTEM, user_prompt, LlmExtraction)
    return result.requirements


def extract_with_llm(chunk: ChunkIn) -> list[FoundRequirement]:
    """Ask the LLM, check the answer, retry once, keep only grounded items.

    Raises:
        LlmUnavailable: Ollama is down. The caller switches to the rules.
    """
    try:
        items = _ask(chunk, [])
    except llm.LlmBadOutput as error:
        items, errors = [], [str(error)]
    else:
        errors = grounding_errors(items, chunk.text)
    if errors:
        try:
            items = _ask(chunk, errors)
        except llm.LlmBadOutput:
            return rules.extract_with_rules(chunk)
    grounded = [item for item in items if grounding.quote_in_text(item.source_quote, chunk.text)]
    return [to_found(item, chunk) for item in grounded]


def deduplicate(found: list[FoundRequirement]) -> list[FoundRequirement]:
    """Drop repeats with the same source sentence (chunks overlap a little)."""
    seen = set()
    unique = []
    for requirement in found:
        key = grounding.normalize(requirement.source_quote)
        if key not in seen:
            seen.add(key)
            unique.append(requirement)
    return unique


if __name__ == "__main__":
    demo = ChunkIn(chunk_index=0, text="The system shall send an OTP to the user's phone within 30 seconds.")
    for requirement in extract_with_llm(demo):
        print(requirement.model_dump_json(indent=2))
