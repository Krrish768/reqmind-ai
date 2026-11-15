"""Download every model listed in configs/weights.yaml.

Models already present are skipped. A failure is reported and the rest still run.

Examples (from the repo root, with Ollama running):
    python -m scripts.download_weights
    python -m scripts.download_weights --section krrish
    python -m scripts.download_weights --name nomic-embed-text
"""
import argparse

import httpx
import ollama
import yaml
from tqdm import tqdm

from backend.app.config import CONFIG_DIR, settings

WEIGHTS_FILE = CONFIG_DIR / "weights.yaml"


def load_entries(section: str | None, name: str | None) -> list[dict]:
    """Entries from weights.yaml, filtered by section and name."""
    sections = yaml.safe_load(WEIGHTS_FILE.read_text()) or {}
    entries = []
    for section_name, items in sections.items():
        if section and section_name != section:
            continue
        entries.extend(item for item in items or [] if not name or item["name"] == name)
    return entries


def installed_models(client: ollama.Client) -> set[str]:
    """Names of models Ollama already has (with and without ":latest")."""
    names = set()
    for model in client.list().models:
        names.add(model.model)
        names.add(model.model.removesuffix(":latest"))
    return names


def pull_with_progress(client: ollama.Client, name: str) -> None:
    """Pull one model and show a progress bar."""
    with tqdm(desc=name, unit="B", unit_scale=True) as bar:
        for update in client.pull(name, stream=True):
            if update.total:
                bar.total = update.total
                bar.n = update.completed or 0
                bar.refresh()


def main() -> None:
    parser = argparse.ArgumentParser(description="Download the models in configs/weights.yaml.")
    parser.add_argument("--section", help="only this teammate's section, e.g. krrish")
    parser.add_argument("--name", help="only this model, e.g. qwen3:8b")
    args = parser.parse_args()

    client = ollama.Client(host=settings.ollama.host)
    try:
        present = installed_models(client)
    except (httpx.HTTPError, ConnectionError) as error:
        print(f"Ollama is not running at {settings.ollama.host} ({error}). Start it with: sudo systemctl start ollama")
        return

    failures = []
    for entry in load_entries(args.section, args.name):
        if entry["name"] in present:
            print(f"skip {entry['name']} (already downloaded)")
            continue
        try:
            pull_with_progress(client, entry["name"])
        except (ollama.ResponseError, httpx.HTTPError, ConnectionError) as error:
            print(f"FAILED {entry['name']}: {error}")
            failures.append(entry["name"])
    print("All models ready." if not failures else f"{len(failures)} failed: {failures}")


if __name__ == "__main__":
    main()
