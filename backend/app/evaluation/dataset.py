"""Load the labelled evaluation documents in samples/eval/.

Each JSON file is one small requirements document written by the team. Every
line has a label: which lines are requirements (with their type and whether
they use vague words), which pairs conflict, which pairs only look like a
conflict (an exception, not a contradiction), and test questions for chat.

Example:
    python -m backend.app.evaluation.dataset
"""
import json
from dataclasses import dataclass, field
from pathlib import Path

from backend.app.config import REPO_ROOT

EVAL_DIR = REPO_ROOT / "samples" / "eval"


@dataclass
class EvalLine:
    text: str
    req_id: str | None  # None for headings and background text
    type: str | None = None
    vague: bool = False


@dataclass
class EvalQuestion:
    question: str
    expect_any: list[str]  # a correct answer contains at least one of these


@dataclass
class EvalDocument:
    name: str
    title: str
    lines: list[EvalLine]
    conflicts: list[tuple[str, str]] = field(default_factory=list)
    lookalikes: list[tuple[str, str]] = field(default_factory=list)
    questions: list[EvalQuestion] = field(default_factory=list)

    @property
    def requirements(self) -> list[EvalLine]:
        """Only the lines labelled as requirements."""
        return [line for line in self.lines if line.req_id]

    def text(self) -> str:
        """The document as plain text, one line per labelled line."""
        return "\n".join(line.text for line in self.lines)


def load_document(path: Path) -> EvalDocument:
    """Read one labelled JSON file."""
    raw = json.loads(path.read_text())
    lines = [EvalLine(text=item["text"], req_id=item["id"], type=item.get("type"), vague=item.get("vague", False))
             for item in raw["lines"]]
    return EvalDocument(
        name=raw["name"], title=raw["title"], lines=lines,
        conflicts=[tuple(pair) for pair in raw["conflicts"]],
        lookalikes=[tuple(pair) for pair in raw["lookalikes"]],
        questions=[EvalQuestion(**item) for item in raw["questions"]],
    )


def load_documents(folder: Path = EVAL_DIR) -> list[EvalDocument]:
    """All labelled documents, sorted by file name."""
    return [load_document(path) for path in sorted(folder.glob("*.json"))]


if __name__ == "__main__":
    for document in load_documents():
        print(f"{document.name:<10} {len(document.requirements):>3} requirements, "
              f"{len(document.conflicts)} conflicts, {len(document.lookalikes)} look-alikes")
