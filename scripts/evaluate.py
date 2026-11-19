"""Score the text rules and the LLM on the labelled documents in samples/eval/.

Saves results/evaluation/<method>/<date_time>/ and prints a short table.
The LLM run needs Ollama with the models; it takes a few minutes.

Examples (from the repo root):
    python -m scripts.evaluate --method rules
    python -m scripts.evaluate --method llm --limit 1
    python -m scripts.evaluate --method both
"""
import argparse

from tqdm import tqdm

from backend.app.evaluation import runner
from backend.app.evaluation.dataset import load_documents


def run_method(method: str, limit: int | None) -> None:
    """Evaluate one method on every document and save the run."""
    use_llm = method == "llm"
    if use_llm:
        runner.check_llm_ready()
    documents = load_documents()[:limit]
    with runner.GpuMonitor() as monitor:
        per_document = [runner.evaluate_document(document, use_llm) for document in tqdm(documents, desc=method)]
    summary = runner.totals(per_document)
    info = runner.run_info(method, monitor.peak_mib if use_llm else None)
    folder = runner.save_run(method, per_document, summary, info)
    print(f"\n{method}: precision {summary['precision']}  recall {summary['recall']}  F1 {summary['f1']}  "
          f"type accuracy {summary['type_accuracy']}")
    print(f"  vague: precision {summary['vague_precision']}  recall {summary['vague_recall']}")
    print(f"  conflicts: {summary['conflicts_correct']} of {summary['conflicts_labelled']} found, "
          f"{summary['conflicts_extra']} false alarms, {summary['lookalikes_reported']} of "
          f"{summary['lookalikes_total']} look-alikes reported")
    if use_llm:
        print(f"  chat: {summary['answers_right']} of {summary['questions']} right, "
              f"{summary['answers_checked']} passed the check")
    print(f"  {summary['seconds_per_document']} s per document. Saved to {folder.relative_to(runner.REPO_ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate requirement extraction, vague words, conflicts and chat.")
    parser.add_argument("--method", choices=["rules", "llm", "both"], default="both")
    parser.add_argument("--limit", type=int, default=None, help="only the first N documents")
    args = parser.parse_args()
    for method in (["rules", "llm"] if args.method == "both" else [args.method]):
        run_method(method, args.limit)


if __name__ == "__main__":
    main()
