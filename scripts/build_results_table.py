"""Build the results tables from the newest saved run of each method.

Reads results/evaluation/<method>/<newest>/metrics.json and run_info.json,
prints Markdown tables and writes them to results/evaluation/summary.md.
Numbers are never typed by hand.

Example (from the repo root, after python -m scripts.evaluate):
    python -m scripts.build_results_table
"""
import argparse
import json

from backend.app.evaluation.runner import RESULTS_DIR

METHOD_NAMES = {"rules": "Text rules", "llm": "qwen3:8b"}


def newest_run(method: str) -> dict | None:
    """Totals and run info of the newest run of a method, or None."""
    runs = sorted((RESULTS_DIR / method).glob("*/metrics.json")) if (RESULTS_DIR / method).exists() else []
    if not runs:
        return None
    folder = runs[-1].parent
    return {"totals": json.loads(runs[-1].read_text())["totals"],
            "info": json.loads((folder / "run_info.json").read_text()), "folder": folder.name}


def show(value: object) -> str:
    """A number for a table cell; "-" when there is none."""
    return "-" if value is None else str(value)


def table(header: list[str], rows: list[list[str]]) -> str:
    """A Markdown table."""
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(lines)


EXTRACTION = [("Labelled requirements", "labelled"), ("Found", "found"), ("Correct", "correct"),
              ("Extra (not a requirement)", "extra"), ("Missed", "missed"), ("Precision", "precision"),
              ("Recall", "recall"), ("F1", "f1"), ("Type accuracy (on correct ones)", "type_accuracy")]
VAGUE = [("Labelled vague", "vague_labelled"), ("Flagged correctly", "vague_correct"),
         ("Flagged but not vague", "vague_extra"), ("Precision", "vague_precision"), ("Recall", "vague_recall")]
CONFLICTS = [("Labelled conflicts", "conflicts_labelled"), ("Found", "conflicts_correct"),
             ("Missed", "conflicts_missed"), ("False alarms", "conflicts_extra"),
             ("Look-alike pairs reported as conflicts", "lookalikes_reported"),
             ("Look-alike pairs in total", "lookalikes_total")]
TIME = [("Seconds per document", "seconds_per_document")]
CHAT = [("Questions", "questions"), ("Passed the grounding check", "answers_checked"),
        ("Right answer", "answers_right"), ("Seconds per question", "seconds_per_question")]


def metric_table(runs: dict[str, dict], metrics: list[tuple[str, str]]) -> str:
    """One row per metric, one column per method."""
    header = ["Metric"] + [METHOD_NAMES[method] for method in runs]
    rows = [[label] + [show(run["totals"].get(key)) for run in runs.values()] for label, key in metrics]
    return table(header, rows)


def build(runs: dict[str, dict]) -> str:
    """All tables for the methods that have a run."""
    parts = ["### Requirement extraction", metric_table(runs, EXTRACTION),
             "### Vague wording", metric_table(runs, VAGUE),
             "### Conflicts", metric_table(runs, CONFLICTS),
             "### Time", metric_table(runs, TIME)]
    if "llm" in runs:
        info = runs["llm"]["info"]
        parts += ["### Chat", metric_table({"llm": runs["llm"]}, CHAT),
                  f"Peak GPU memory during the LLM run: {show(info['gpu_peak_mib'])} MiB on {show(info['gpu'])}."]
    sources = ", ".join(f"`results/evaluation/{method}/{run['folder']}`" for method, run in runs.items())
    return "\n\n".join(parts) + f"\n\nSource runs: {sources}.\n"


def main() -> None:
    argparse.ArgumentParser(description="Build the results tables from the saved runs.").parse_args()
    runs = {method: run for method in METHOD_NAMES if (run := newest_run(method))}
    if not runs:
        raise SystemExit("No runs in results/evaluation/. Run: python -m scripts.evaluate")
    text = "## Evaluation results\n\n" + build(runs)
    (RESULTS_DIR / "summary.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
