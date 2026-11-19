"""Run the analysis on every labelled document, score it and save the results.

Results go to results/evaluation/<method>/<date_time>/:
metrics.json (totals), per_document.csv and run_info.json (config, models,
git commit, seed, hardware). The same chunking and agents as the app are used,
but no database, queue or web server.
"""
import csv
import json
import os
import platform
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

from backend.app.agents.workflow import AnalysisState, run_workflow
from backend.app.config import REPO_ROOT, settings
from backend.app.evaluation import scoring
from backend.app.evaluation.dataset import EvalDocument
from backend.app.ingestion.chunking import chunk_pages
from backend.app.ingestion.parsing import PageText
from backend.app.llm import client as llm
from backend.app.rag.chat import ask_llm
from backend.app.schemas import ChunkIn

RESULTS_DIR = REPO_ROOT / "results" / "evaluation"
COUNT_KEYS = ["labelled", "found", "correct", "extra", "missed", "type_correct", "vague_labelled", "vague_correct",
              "vague_extra", "vague_missed", "conflicts_labelled", "conflicts_correct", "conflicts_extra",
              "conflicts_missed", "lookalikes_reported", "lookalikes_total", "questions", "answers_checked",
              "answers_right", "seconds", "chat_seconds"]


class GpuMonitor:
    """Reads the used GPU memory twice a second in the background and keeps the highest value."""

    def __init__(self) -> None:
        self.peak_mib: int | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._poll, daemon=True)

    def _read(self) -> int | None:
        output = command_output(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"])
        return int(output.split()[0]) if output else None

    def _poll(self) -> None:
        while not self._stop.is_set():
            used = self._read()
            if used is not None:
                self.peak_mib = max(self.peak_mib or 0, used)
            self._stop.wait(0.5)

    def __enter__(self) -> "GpuMonitor":
        self._thread.start()
        return self

    def __exit__(self, *_args: object) -> None:
        self._stop.set()
        self._thread.join()


def make_chunks(document: EvalDocument) -> list[ChunkIn]:
    """Chunks of the document, cut the same way as an upload."""
    pages = [PageText(page=None, text=document.text())]
    chunks = chunk_pages(pages, settings.ingestion.chunk_chars, settings.ingestion.overlap_chars)
    return [ChunkIn(chunk_index=chunk.chunk_index, text=chunk.text) for chunk in chunks]


def ask_questions(document: EvalDocument, chunks: list[ChunkIn]) -> dict:
    """Ask each test question with the document's chunks as passages.

    An answer is "checked" when it passed the grounding check, and "right"
    when it also contains one of the expected words.
    """
    passages = [{"text": chunk.text} for chunk in chunks[: settings.chat.top_k]]
    checked = right = 0
    answers = []
    for item in document.questions:
        answer = ask_llm(item.question, passages)
        is_right = answer is not None and any(word.lower() in answer.answer.lower() for word in item.expect_any)
        checked += answer is not None
        right += is_right
        answers.append({"question": item.question, "answer": answer.answer if answer else None, "right": is_right})
    return {"questions": len(document.questions), "answers_checked": checked, "answers_right": right,
            "answers": answers}


def score_document(document: EvalDocument, state: AnalysisState) -> dict:
    """All counts for one document."""
    found = state["found"]
    matches = scoring.match_requirements(found, document.requirements)
    counts = {"document": document.name, "labelled": len(document.requirements), "found": len(found),
              "vague_labelled": sum(label.vague for label in document.requirements),
              "conflicts_labelled": len(document.conflicts), "notes": state["notes"]}
    counts.update(scoring.extraction_counts(found, document, matches))
    counts.update(scoring.vague_counts(found, document, matches))
    counts.update(scoring.conflict_counts(state["conflicts"], document, matches))
    return counts


def evaluate_document(document: EvalDocument, use_llm: bool) -> dict:
    """Analyze one document, score it and, with the LLM, ask its questions."""
    chunks = make_chunks(document)
    started = time.perf_counter()
    state = run_workflow(chunks, use_llm=use_llm, report=lambda _percent, _message: None)
    result = score_document(document, state)
    result["seconds"] = round(time.perf_counter() - started, 1)
    result["chunks"] = len(chunks)
    if use_llm:
        started = time.perf_counter()
        result.update(ask_questions(document, chunks))
        result["chat_seconds"] = round(time.perf_counter() - started, 1)
    return result


def totals(per_document: list[dict]) -> dict:
    """Sum the counts over all documents and work out the rates."""
    total = {key: sum(row.get(key, 0) for row in per_document) for key in COUNT_KEYS}
    precision = scoring.ratio(total["correct"], total["found"])
    recall = scoring.ratio(total["correct"], total["labelled"])
    total.update({
        "precision": precision, "recall": recall, "f1": scoring.f1(precision, recall),
        "type_accuracy": scoring.ratio(total["type_correct"], total["correct"]),
        "vague_precision": scoring.ratio(total["vague_correct"], total["vague_correct"] + total["vague_extra"]),
        "vague_recall": scoring.ratio(total["vague_correct"], total["vague_labelled"]),
        "seconds_per_document": round(total["seconds"] / max(len(per_document), 1), 1),
        "seconds_per_question": round(total["chat_seconds"] / total["questions"], 1) if total["questions"] else None,
    })
    return total


def command_output(command: list[str]) -> str | None:
    """Output of a shell command, or None if it is not installed or fails."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, cwd=REPO_ROOT, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() or None if result.returncode == 0 else None


def run_info(method: str, gpu_peak_mib: int | None) -> dict:
    """Everything needed to repeat the run."""
    commit = command_output(["git", "rev-parse", "--short", "HEAD"])
    gpu = command_output(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"]) if method == "llm" else None
    return {"method": method, "date": datetime.now().isoformat(timespec="seconds"), "git_commit": commit,
            "config": settings.config_name, "llm_model": settings.ollama.llm_model if method == "llm" else None,
            "embed_model": settings.ollama.embed_model if method == "llm" else None, "seed": settings.seed,
            "num_ctx": settings.ollama.num_ctx, "conflict_similarity": settings.analysis.conflict_similarity,
            "gpu": gpu, "gpu_peak_mib": gpu_peak_mib, "cpu_count": os.cpu_count(),
            "python": platform.python_version()}


def save_run(method: str, per_document: list[dict], summary: dict, info: dict) -> Path:
    """Write metrics.json, per_document.csv and run_info.json; return the folder."""
    folder = RESULTS_DIR / method / datetime.now().strftime("%Y%m%d_%H%M%S")
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "metrics.json").write_text(json.dumps({"totals": summary, "documents": per_document}, indent=2) + "\n")
    (folder / "run_info.json").write_text(json.dumps(info, indent=2) + "\n")
    with (folder / "per_document.csv").open("w", newline="") as handle:
        columns = ["document"] + [key for key in COUNT_KEYS if key in per_document[0]]
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(per_document)
    return folder


def check_llm_ready() -> None:
    """Stop early with a clear message if Ollama or a model is missing."""
    status = llm.ollama_status()
    if status != "ok":
        raise SystemExit(f"Ollama is not ready: {status}")
