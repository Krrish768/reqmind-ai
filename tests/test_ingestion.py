"""Parsing PDF, DOCX and text files, and cutting them into chunks."""
import io

import docx
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from backend.app.ingestion import chunking, parsing
from backend.app.ingestion.parsing import PageText


def make_pdf(pages: list[list[str]]) -> bytes:
    """A PDF with the given lines on each page."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    for lines in pages:
        for number, line in enumerate(lines):
            pdf.drawString(72, 760 - 18 * number, line)
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def make_docx(paragraphs: list[str], table_rows: list[list[str]] = ()) -> bytes:
    """A Word file with paragraphs and an optional table."""
    document = docx.Document()
    for text in paragraphs:
        document.add_paragraph(text)
    if table_rows:
        table = document.add_table(rows=0, cols=len(table_rows[0]))
        for row in table_rows:
            for cell, text in zip(table.add_row().cells, row):
                cell.text = text
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def test_pdf_keeps_page_numbers() -> None:
    data = make_pdf([["The system shall log in users."], ["The system shall send receipts."]])
    pages = parsing.parse_file("srs.pdf", data)
    assert [page.page for page in pages] == [1, 2]
    assert "send receipts" in pages[1].text


def test_docx_reads_paragraphs_and_tables() -> None:
    data = make_docx(["Students shall sign up."], [["REQ-9", "The app shall work offline."]])
    text = parsing.parse_file("srs.docx", data)[0].text
    assert "Students shall sign up." in text
    assert "REQ-9 | The app shall work offline." in text


def test_text_file_with_latin1() -> None:
    pages = parsing.parse_file("notes.txt", "Café menu shall load.".encode("latin-1"))
    assert pages[0].text == "Café menu shall load."


@pytest.mark.parametrize("filename, data, message", [
    ("photo.png", b"x", "We can read PDF"),
    ("empty.txt", b"   \n ", "could not find any text"),
    ("broken.pdf", b"not a pdf", "could not be read"),
    ("broken.docx", b"not a docx", "could not be read"),
])
def test_bad_files_get_a_clear_reason(filename: str, data: bytes, message: str) -> None:
    with pytest.raises(parsing.ParseError, match=message):
        parsing.parse_file(filename, data)


def test_chunks_are_exact_slices_of_the_page() -> None:
    text = "\n".join(f"- The system shall do task number {n}." for n in range(1, 60))
    chunks = chunking.chunk_pages([PageText(page=3, text=text)], chunk_chars=300, overlap_chars=60)
    assert len(chunks) > 3
    for chunk in chunks:
        assert chunk.text == text[chunk.char_start:chunk.char_end]
        assert len(chunk.text) <= 300
        assert chunk.page == 3
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))


def test_chunks_overlap_and_cover_every_line() -> None:
    text = "\n".join(f"Line {n} shall be kept." for n in range(1, 40))
    chunks = chunking.chunk_pages([PageText(page=None, text=text)], chunk_chars=200, overlap_chars=50)
    joined = "\n".join(chunk.text for chunk in chunks)
    assert all(f"Line {n} shall" in joined for n in range(1, 40))
    assert chunks[1].text.splitlines()[0] in chunks[0].text


def test_a_very_long_line_is_split_at_sentences() -> None:
    line = " ".join(f"Sentence {n} shall be short." for n in range(1, 80))
    chunks = chunking.chunk_pages([PageText(page=None, text=line)], chunk_chars=250, overlap_chars=0)
    assert all(len(chunk.text) <= 250 for chunk in chunks)
    assert all(chunk.text.rstrip().endswith(".") for chunk in chunks)


def test_chunk_numbers_continue_across_pages() -> None:
    pages = [PageText(page=1, text="A shall work."), PageText(page=2, text="B shall work.")]
    chunks = chunking.chunk_pages(pages, chunk_chars=500, overlap_chars=50)
    assert [(chunk.chunk_index, chunk.page) for chunk in chunks] == [(0, 1), (1, 2)]
