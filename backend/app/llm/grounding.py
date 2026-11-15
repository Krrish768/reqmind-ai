"""Checks that what the LLM wrote really comes from the given text.

Example:
    python -m backend.app.llm.grounding
"""
import re

NUMBER_PATTERN = re.compile(r"\d+(?:[.,]\d+)?")
QUOTE_CHARS = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})


def normalize(text: str) -> str:
    """Lowercase, plain quotes, single spaces, no punctuation at the ends."""
    text = text.translate(QUOTE_CHARS).lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text.strip(" .,;:!?\"'-*•")


def quote_in_text(quote: str, text: str) -> bool:
    """True if the quote appears in the text (after normalizing both)."""
    clean_quote = normalize(quote)
    return bool(clean_quote) and clean_quote in normalize(text)


def entity_in_text(entity: str, text: str) -> bool:
    """True if the entity, or its singular form, appears in the text."""
    clean_entity = normalize(entity)
    clean_text = normalize(text)
    if not clean_entity:
        return False
    return clean_entity in clean_text or clean_entity.rstrip("s") in clean_text


def numbers_in(text: str) -> set[str]:
    """All numbers written in the text, like {"5", "99.9"}."""
    return {number.replace(",", ".") for number in NUMBER_PATTERN.findall(text)}


def unsupported_numbers(answer: str, facts: str) -> list[str]:
    """Numbers in the answer that do not appear anywhere in the facts."""
    allowed = numbers_in(facts)
    return sorted(number for number in numbers_in(answer) if number not in allowed)


if __name__ == "__main__":
    chunk = "The system shall lock the account after 5 failed logins."
    print(quote_in_text("the system shall lock the account after 5 failed logins", chunk))
    print(entity_in_text("accounts", chunk))
    print(unsupported_numbers("It locks after 3 tries.", chunk))
