"""Run the analysis from the command line and print what was found.

Two modes:
  --chunks FILE      run the agents on a chunks JSON file (no database needed)
  --document-id N    run the full pipeline on a saved document (database needed)

Examples (from the repo root):
    python -m scripts.analyze_document --chunks samples/chunks.json --limit 2
    python -m scripts.analyze_document --chunks samples/chunks.json --rules
    python -m scripts.analyze_document --document-id 1
"""
import argparse
import json
import time
from pathlib import Path

from tqdm import tqdm

from backend.app import models
from backend.app.agents.workflow import AnalysisState, run_workflow
from backend.app.config import settings
from backend.app.database import SessionLocal, create_tables
from backend.app.pipeline import analyze_document
from backend.app.schemas import ChunkIn


def print_results(state: AnalysisState) -> None:
    """One line per requirement and per conflict."""
    for number, item in enumerate(state["found"]):
        flag = " [vague]" if item.is_ambiguous else ""
        print(f"{number:>3} {item.priority:<6} {item.type:<14} {item.title}{flag}")
    for conflict in state["conflicts"]:
        print(f"conflict {conflict.index_a} <-> {conflict.index_b}: {conflict.reason}")
    for note in state["notes"]:
        print(f"note: {note}")


def run_on_file(path: Path, limit: int | None, use_llm: bool) -> None:
    """Run the agents on chunks from a JSON file."""
    chunks = [ChunkIn(**item) for item in json.loads(path.read_text())][:limit]
    bar = tqdm(total=100, desc="analysis")

    def report(percent: int, message: str) -> None:
        bar.set_postfix_str(message)
        bar.update(max(0, percent - bar.n))

    started = time.perf_counter()
    state = run_workflow(chunks, use_llm=use_llm, report=report)
    bar.update(100 - bar.n)
    bar.close()
    print_results(state)
    print(f"{len(state['found'])} requirements, {len(state['conflicts'])} conflicts "
          f"from {len(chunks)} chunks in {time.perf_counter() - started:.1f} s")


def run_on_document(document_id: int) -> None:
    """Run the full pipeline on one document in the database."""
    create_tables()
    db = SessionLocal()
    try:
        document = db.get(models.Document, document_id)
        if document is None:
            print(f"No document with id {document_id}.")
            return
        summary = analyze_document(db, document, lambda percent, message: print(f"{percent:3d}% {message}"))
        print(summary.message())
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the requirement analysis.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--chunks", type=Path, help="chunks JSON file, e.g. samples/chunks.json")
    source.add_argument("--document-id", type=int, help="id of a document in the database")
    parser.add_argument("--limit", type=int, default=None, help="only the first N chunks (with --chunks)")
    parser.add_argument("--rules", action="store_true", help="use the text rules, not the LLM (with --chunks)")
    args = parser.parse_args()

    if args.document_id is not None:
        run_on_document(args.document_id)
    else:
        run_on_file(args.chunks, args.limit, use_llm=settings.ai_enabled and not args.rules)


if __name__ == "__main__":
    main()
