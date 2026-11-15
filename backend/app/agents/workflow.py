"""The analysis as a LangGraph workflow: extract -> deduplicate -> embed -> conflicts.

Each step is one agent node. If Ollama goes down in the middle, the nodes
switch to the text rules and note it, so the job still finishes.

Example:
    APP_CONFIG=cpu_laptop python -m backend.app.agents.workflow
"""
from collections.abc import Callable
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from backend.app.agents import conflicts, extraction, rules
from backend.app.llm import client as llm
from backend.app.schemas import ChunkIn, FoundConflict, FoundRequirement

ProgressFn = Callable[[int, str], None]
LLM_DOWN_NOTE = "The LLM was not reachable, so text rules were used from here on."


class AnalysisState(TypedDict):
    chunks: list[ChunkIn]
    use_llm: bool
    found: list[FoundRequirement]
    vectors: list[list[float]] | None
    conflicts: list[FoundConflict]
    notes: list[str]


def _extract_chunk(chunk: ChunkIn, use_llm: bool) -> tuple[list[FoundRequirement], bool]:
    """Extract from one chunk; returns the items and whether the LLM is still usable."""
    if not use_llm:
        return rules.extract_with_rules(chunk), False
    try:
        return extraction.extract_with_llm(chunk), True
    except llm.LlmUnavailable:
        return rules.extract_with_rules(chunk), False


def make_extract_node(report: ProgressFn) -> Callable[[AnalysisState], dict]:
    """Node that finds requirements chunk by chunk (progress 5% to 60%)."""
    def extract_node(state: AnalysisState) -> dict:
        use_llm = state["use_llm"]
        notes = list(state["notes"])
        found: list[FoundRequirement] = []
        total = len(state["chunks"])
        for number, chunk in enumerate(state["chunks"], start=1):
            report(5 + int(55 * (number - 1) / total), f"Finding requirements ({number}/{total})")
            items, still_usable = _extract_chunk(chunk, use_llm)
            if use_llm and not still_usable:
                notes.append(LLM_DOWN_NOTE)
            use_llm = still_usable
            found.extend(items)
        return {"found": found, "use_llm": use_llm, "notes": notes}
    return extract_node


def deduplicate_node(state: AnalysisState) -> dict:
    """Remove requirements that came from the same sentence."""
    return {"found": extraction.deduplicate(state["found"])}


def make_embed_node(report: ProgressFn) -> Callable[[AnalysisState], dict]:
    """Node that embeds requirement texts for the similarity check (progress 65%)."""
    def embed_node(state: AnalysisState) -> dict:
        if not state["use_llm"]:
            return {"vectors": None}
        report(65, "Comparing requirements")
        try:
            vectors = llm.embed_texts([requirement.description for requirement in state["found"]])
        except llm.LlmUnavailable:
            return {"vectors": None, "use_llm": False, "notes": state["notes"] + [LLM_DOWN_NOTE]}
        return {"vectors": vectors}
    return embed_node


def make_conflict_node(report: ProgressFn) -> Callable[[AnalysisState], dict]:
    """Node that finds contradicting pairs (progress 75%)."""
    def conflict_node(state: AnalysisState) -> dict:
        report(75, "Checking for conflicts")
        try:
            found_conflicts = conflicts.detect_conflicts(state["found"], state["vectors"], state["use_llm"])
        except llm.LlmUnavailable:
            found_conflicts = conflicts.detect_conflicts(state["found"], state["vectors"], use_llm=False)
            return {"conflicts": found_conflicts, "use_llm": False, "notes": state["notes"] + [LLM_DOWN_NOTE]}
        return {"conflicts": found_conflicts}
    return conflict_node


def _after_deduplicate(state: AnalysisState) -> str:
    """Stop early when nothing was found."""
    return "embed" if state["found"] else END


def build_workflow(report: ProgressFn) -> CompiledStateGraph:
    """Wire the nodes into a compiled LangGraph graph."""
    graph = StateGraph(AnalysisState)
    graph.add_node("extract", make_extract_node(report))
    graph.add_node("deduplicate", deduplicate_node)
    graph.add_node("embed", make_embed_node(report))
    graph.add_node("conflicts", make_conflict_node(report))
    graph.add_edge(START, "extract")
    graph.add_edge("extract", "deduplicate")
    graph.add_conditional_edges("deduplicate", _after_deduplicate, ["embed", END])
    graph.add_edge("embed", "conflicts")
    graph.add_edge("conflicts", END)
    return graph.compile()


def run_workflow(chunks: list[ChunkIn], use_llm: bool, report: ProgressFn) -> AnalysisState:
    """Run the whole analysis on a list of chunks.

    Args:
        chunks: Chunks of one document, in order.
        use_llm: False to use only the text rules.
        report: Called with (percent, message) as the work moves on.

    Returns:
        The final state with found requirements, conflicts and notes.
    """
    start: AnalysisState = {"chunks": chunks, "use_llm": use_llm, "found": [], "vectors": None,
                            "conflicts": [], "notes": []}
    return build_workflow(report).invoke(start)


if __name__ == "__main__":
    import json

    from backend.app.config import REPO_ROOT

    sample = [ChunkIn(**item) for item in json.loads((REPO_ROOT / "samples" / "chunks.json").read_text())]
    final = run_workflow(sample, use_llm=False, report=lambda percent, message: print(f"{percent:3d}% {message}"))
    print(f"{len(final['found'])} requirements, {len(final['conflicts'])} conflicts")
