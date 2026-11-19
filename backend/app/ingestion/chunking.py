"""Cut page text into chunks of about ingestion.chunk_chars characters.

Chunks end at line or sentence breaks, never in the middle of a word, and the
last lines of a chunk are repeated at the start of the next one
(ingestion.overlap_chars) so a requirement on the border is not lost.
The chunk text is an exact slice of the page text, so quotes can be found in it.

Example:
    python -m backend.app.ingestion.chunking
"""
import re
from dataclasses import dataclass

from backend.app.ingestion.parsing import PageText

SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
Span = tuple[int, int]


@dataclass
class TextChunk:
    chunk_index: int
    text: str
    page: int | None
    char_start: int
    char_end: int


def line_spans(text: str) -> list[Span]:
    """(start, end) of every non-empty line."""
    spans = []
    for match in re.finditer(r"[^\n]+", text):
        if match.group().strip():
            spans.append((match.start(), match.end()))
    return spans


def split_long_span(text: str, span: Span, max_chars: int) -> list[Span]:
    """Split a span longer than max_chars at sentence ends, then at spaces."""
    start, end = span
    if end - start <= max_chars:
        return [span]
    pieces = []
    while end - start > max_chars:
        window = text[start:start + max_chars]
        breaks = [match.end() for match in SENTENCE_END.finditer(window)] or [window.rfind(" ") + 1]
        cut = start + (breaks[-1] if breaks[-1] > 0 else max_chars)
        pieces.append((start, cut))
        start = cut
    pieces.append((start, end))
    return pieces


def units_of(text: str, max_chars: int) -> list[Span]:
    """Line spans, with long lines split so none is longer than max_chars."""
    units = []
    for span in line_spans(text):
        units.extend(split_long_span(text, span, max_chars))
    return units


def _overlap_start(units: list[Span], first: int, last: int, overlap_chars: int) -> int:
    """Index of the first unit to repeat in the next chunk."""
    index = last + 1
    while index - 1 > first and units[last][1] - units[index - 1][0] <= overlap_chars:
        index -= 1
    return index


def group_units(units: list[Span], chunk_chars: int, overlap_chars: int) -> list[Span]:
    """Join units into chunk spans of at most chunk_chars characters."""
    chunks = []
    first = 0
    while first < len(units):
        last = first
        while last + 1 < len(units) and units[last + 1][1] - units[first][0] <= chunk_chars:
            last += 1
        chunks.append((units[first][0], units[last][1]))
        if last + 1 >= len(units):
            break
        first = _overlap_start(units, first, last, overlap_chars)
    return chunks


def chunk_pages(pages: list[PageText], chunk_chars: int, overlap_chars: int) -> list[TextChunk]:
    """Chunks of all pages, numbered from 0 across the whole document."""
    chunks = []
    for page in pages:
        units = units_of(page.text, chunk_chars)
        for start, end in group_units(units, chunk_chars, overlap_chars):
            chunks.append(TextChunk(chunk_index=len(chunks), text=page.text[start:end], page=page.page,
                                    char_start=start, char_end=end))
    return chunks


if __name__ == "__main__":
    demo = PageText(page=1, text="\n".join(f"- The system shall do task number {n}." for n in range(1, 30)))
    for chunk in chunk_pages([demo], chunk_chars=300, overlap_chars=60):
        print(chunk.chunk_index, chunk.char_start, chunk.char_end, chunk.text.splitlines()[0])
