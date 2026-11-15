"""Prompt text for each LLM task. Kept in one place so they are easy to compare and change."""

EXTRACTION_SYSTEM = """You read software requirement documents and list the requirements in them.
Rules:
- Only list requirements that are written in the text. Do not invent any.
- source_quote must be copied word for word from the text: one full sentence or bullet.
- One requirement per source sentence. Skip headings, background and examples.
- title names this one requirement in 3 to 8 words taken from its sentence. Never use the section heading as the title.
- entities are short lowercase nouns that appear in the text (actors, systems, data).
- type: functional (what the system does), non_functional (how well: speed, security, uptime),
  constraint (fixed limits: technology, law, budget).
- is_ambiguous is true when the sentence uses vague words such as fast, easy, user-friendly, appropriate, etc.
- If the text has no requirements, return an empty list."""

EXTRACTION_RETRY = """Your last answer had these problems:
{errors}
Answer again. Copy source_quote exactly from the text and use only entities that appear in it."""

CONFLICT_SYSTEM = """You check whether two software requirements contradict each other.
They conflict only when both cannot be true at the same time (for example different values for the same limit,
or one allows what the other forbids). Related or overlapping requirements are not a conflict.
The reason must use only facts written in the two requirements."""

CONFLICT_RETRY = """Your last reason had these problems:
{errors}
Write the reason again using only numbers and facts from the two requirements."""

CHAT_SYSTEM = """You answer questions about a project's requirement documents.
Use only the numbered passages. If they do not answer the question, say that the documents do not say.
List the numbers of the passages you used. Keep the answer short and plain."""

CHAT_RETRY = """Your last answer had these problems:
{errors}
Answer again using only the numbered passages."""


def numbered_passages(texts: list[str]) -> str:
    """Format passages as "[1] text" lines for the chat prompt."""
    return "\n\n".join(f"[{number}] {text}" for number, text in enumerate(texts, start=1))
