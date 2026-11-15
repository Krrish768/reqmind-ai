"""Simple text rules for requirements.

They decide priority and vague words for every requirement, and they are the
fallback extractor when the LLM is off or down. They are also the baseline the
LLM extraction is compared against.

Example:
    python -m backend.app.agents.rules
"""
import re

from backend.app.schemas import ChunkIn, FoundRequirement, Priority, RequirementType

MODAL_PATTERN = re.compile(
    r"\b(shall|must|is required to|are required to|should|will|needs to|need to|may|could)\b", re.IGNORECASE
)
HIGH_MODALS = {"shall", "must", "is required to", "are required to"}
LOW_MODALS = {"may", "could"}
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
BULLET_PREFIX = re.compile(r"^\s*(?:[-*•]|\d+[.)]|[A-Z]{2,}-\d+[:.)]?)\s*")
LEADING_WORDS = {"the", "a", "an", "each", "every", "all", "any"}
TITLE_WORDS = 8

VAGUE_WORDS = [
    "fast", "quick", "quickly", "easy", "easily", "user-friendly", "user friendly", "intuitive",
    "appropriate", "adequate", "efficient", "flexible", "simple", "as soon as possible", "etc",
    "and/or", "reasonable", "minimal", "several", "some", "normal", "good",
]
CONSTRAINT_WORDS = ["comply", "compliant", "gdpr", "law", "budget", "licence", "license", "must be written in",
                    "only use", "must use", "must run on", "browser", "operating system"]
NON_FUNCTIONAL_WORDS = ["within", "second", "seconds", "millisecond", " ms", "minutes", "%", "percent", "uptime",
                        "available", "availability", "encrypt", "secure", "performance", "response time",
                        "concurrent", "at the same time", "scale", "backup"]
CATEGORY_WORDS = {
    "security": ["password", "encrypt", "login", "log in", "authenticat", "role", "access", "otp"],
    "performance": ["second", "response time", "concurrent", "load", "millisecond", "at the same time"],
    "reliability": ["uptime", "available", "availability", "backup", "recover"],
    "usability": ["easy", "user-friendly", "intuitive", "accessib"],
    "integration": ["api", "payment gateway", "email", "sms", "third-party", "upi"],
    "ui": ["screen", "page", "button", "display", "dashboard", "menu"],
    "data": ["store", "database", "record", "report", "export", "history"],
}


def split_sentences(text: str) -> list[str]:
    """Split text into sentences and bullet lines, without bullet markers."""
    sentences = []
    for line in text.splitlines():
        line = BULLET_PREFIX.sub("", line).strip()
        for part in SENTENCE_SPLIT.split(line):
            if part.strip():
                sentences.append(part.strip())
    return sentences


def strongest_modal(sentence: str) -> str | None:
    """The strongest modal verb in the sentence ("must" beats "should"), or None."""
    found = [match.lower() for match in MODAL_PATTERN.findall(sentence)]
    for group in (HIGH_MODALS, {"should", "will", "needs to", "need to"}, LOW_MODALS):
        for modal in found:
            if modal in group:
                return modal
    return None


def priority_from_text(sentence: str) -> Priority:
    """must/shall -> high, should/will -> medium, may/could -> low."""
    modal = strongest_modal(sentence)
    if modal in HIGH_MODALS:
        return "high"
    if modal in LOW_MODALS:
        return "low"
    return "medium"


def vague_words_in(sentence: str) -> list[str]:
    """Vague words used in the sentence, in the order of VAGUE_WORDS."""
    lowered = f" {sentence.lower()} "
    return [word for word in VAGUE_WORDS if re.search(rf"(?<![\w-]){re.escape(word)}(?![\w-])", lowered)]


def type_from_text(sentence: str) -> RequirementType:
    """Guess the requirement type from key words."""
    lowered = sentence.lower()
    if any(word in lowered for word in CONSTRAINT_WORDS):
        return "constraint"
    if any(word in lowered for word in NON_FUNCTIONAL_WORDS):
        return "non_functional"
    return "functional"


def category_from_text(sentence: str) -> str:
    """Guess the category from key words, "other" if nothing matches."""
    lowered = sentence.lower()
    for category, words in CATEGORY_WORDS.items():
        if any(word in lowered for word in words):
            return category
    return "other"


def subject_entity(sentence: str) -> list[str]:
    """The subject before the modal verb ("The mobile app shall" -> ["mobile app"])."""
    match = MODAL_PATTERN.search(sentence)
    if not match:
        return []
    words = [word.strip(",;:").lower() for word in sentence[: match.start()].split()][-3:]
    while words and words[0] in LEADING_WORDS:
        words = words[1:]
    return [" ".join(words)] if words and all(word.isalpha() for word in words) else []


def make_title(sentence: str) -> str:
    """First words after the modal verb, as a short title."""
    match = MODAL_PATTERN.search(sentence)
    rest = sentence[match.end():] if match else sentence
    words = rest.strip(" .").split()[:TITLE_WORDS] or sentence.split()[:TITLE_WORDS]
    title = " ".join(words).strip(" ,;:")
    return title[:1].upper() + title[1:]


def extract_with_rules(chunk: ChunkIn) -> list[FoundRequirement]:
    """Every sentence with a modal verb becomes one requirement."""
    found = []
    for sentence in split_sentences(chunk.text):
        if not strongest_modal(sentence) or len(sentence.split()) < 4:
            continue
        vague = vague_words_in(sentence)
        found.append(FoundRequirement(
            title=make_title(sentence),
            description=sentence,
            type=type_from_text(sentence),
            category=category_from_text(sentence),
            priority=priority_from_text(sentence),
            source_quote=sentence,
            entities=subject_entity(sentence),
            is_ambiguous=bool(vague),
            ambiguity_note=vague_note(vague),
            chunk_index=chunk.chunk_index,
            chunk_id=chunk.chunk_id,
            method="rules",
        ))
    return found


def vague_note(vague_words: list[str]) -> str | None:
    """A short note listing the vague words, or None."""
    if not vague_words:
        return None
    return "Vague words: " + ", ".join(f'"{word}"' for word in vague_words)


if __name__ == "__main__":
    demo = ChunkIn(chunk_index=0, text="- The system shall respond fast.\n- Students may save favourite items.")
    for requirement in extract_with_rules(demo):
        print(requirement.priority, requirement.type, requirement.title, requirement.ambiguity_note)
