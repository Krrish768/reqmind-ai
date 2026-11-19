"""Turn an uploaded file into plain text, page by page.

PDF keeps its page numbers; DOCX, TXT and MD give one page without a number.

Example:
    python -m backend.app.ingestion.parsing path/to/file.pdf
"""
import io
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

import docx
from docx.document import Document as DocxDocument
from pypdf import PdfReader
from pypdf.errors import PdfReadError

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
}


@dataclass
class PageText:
    page: int | None  # 1-based PDF page, None for other files
    text: str


class ParseError(Exception):
    """The file could not be read, or it has no text."""


def extension_of(filename: str) -> str:
    """Lowercase extension with the dot, like ".pdf"."""
    return Path(filename).suffix.lower()


def parse_pdf(data: bytes) -> list[PageText]:
    """Text of every PDF page."""
    try:
        reader = PdfReader(io.BytesIO(data))
        return [PageText(page=number, text=page.extract_text() or "")
                for number, page in enumerate(reader.pages, start=1)]
    except (PdfReadError, ValueError) as error:
        raise ParseError(f"This PDF could not be read ({error}).") from error


def _table_lines(document: DocxDocument) -> list[str]:
    """Each table row as one line, cells joined with " | "."""
    lines = []
    for table in document.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                lines.append(" | ".join(cells))
    return lines


def parse_docx(data: bytes) -> list[PageText]:
    """Paragraphs and table rows of a Word file as one page."""
    try:
        document = docx.Document(io.BytesIO(data))
    except (ValueError, KeyError, OSError, zipfile.BadZipFile) as error:
        raise ParseError(f"This Word file could not be read ({error}).") from error
    paragraphs = [paragraph.text for paragraph in document.paragraphs]
    return [PageText(page=None, text="\n".join(paragraphs + _table_lines(document)))]


def parse_text(data: bytes) -> list[PageText]:
    """A TXT or MD file as one page (UTF-8, with a Latin-1 fallback)."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    return [PageText(page=None, text=text)]


def parse_file(filename: str, data: bytes) -> list[PageText]:
    """Pick the parser by extension and check that some text came out.

    Raises:
        ParseError: Unknown type, unreadable file, or no text (for example a scanned PDF).
    """
    extension = extension_of(filename)
    if extension not in ALLOWED_EXTENSIONS:
        raise ParseError(f"We can read PDF, DOCX, TXT and MD files, not {extension or 'this file type'}.")
    if extension == ".pdf":
        pages = parse_pdf(data)
    elif extension == ".docx":
        pages = parse_docx(data)
    else:
        pages = parse_text(data)
    if not any(page.text.strip() for page in pages):
        raise ParseError("We could not find any text in this file. Scanned PDFs are not supported.")
    return pages


if __name__ == "__main__":
    file_path = Path(sys.argv[1])
    for page_text in parse_file(file_path.name, file_path.read_bytes()):
        print(f"--- page {page_text.page} ({len(page_text.text)} characters)")
        print(page_text.text[:300])
