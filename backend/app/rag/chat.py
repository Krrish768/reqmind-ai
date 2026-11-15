"""Answer a question about a project from its document chunks.

Passages come from Qdrant (vector search) or, when that is not available,
from a simple keyword search in Postgres. The LLM writes the answer only from
the numbered passages, and the answer is checked: the passage numbers must
exist and every number in the answer must appear in the passages. If the
check fails twice, or the LLM is off, a fixed template lists the passages.
"""
import re

from sqlalchemy.orm import Session

from backend.app import models
from backend.app.config import settings
from backend.app.llm import client as llm
from backend.app.llm import grounding, prompts
from backend.app.rag import vector_store
from backend.app.schemas import ChatResponse, ChatSource, LlmChatAnswer

NO_PASSAGES = "None of the documents in this project match this question yet."
TEMPLATE_AI_OFF = "AI answers are turned off on this machine. These passages match your question best."
TEMPLATE_UNCHECKED = "We could not write an answer that we could check, so here are the passages that match best."
QUESTION_WORD = re.compile(r"[a-z0-9]{3,}")


def keyword_search(db: Session, project: models.Project, question: str, top_k: int) -> list[dict]:
    """Chunks of the project ranked by how many question words they contain."""
    words = set(QUESTION_WORD.findall(question.lower()))
    rows = (
        db.query(models.DocumentChunk, models.Document.filename)
        .join(models.Document, models.Document.id == models.DocumentChunk.document_id)
        .filter(models.Document.project_id == project.id, models.Document.company_id == project.company_id)
        .all()
    )
    scored = []
    for chunk, filename in rows:
        score = sum(1 for word in words if word in chunk.text.lower())
        if score:
            scored.append({"document_id": chunk.document_id, "filename": filename,
                           "chunk_index": chunk.chunk_index, "text": chunk.text, "score": score})
    scored.sort(key=lambda passage: -passage["score"])
    return scored[:top_k]


def vector_search(project: models.Project, question: str, top_k: int) -> list[dict]:
    """Closest chunks from Qdrant.

    Raises:
        LlmUnavailable: the question could not be embedded.
    """
    vector = llm.embed_texts([question], is_query=True)[0]
    return vector_store.search(project.company_id, project.id, vector, top_k)


def find_passages(db: Session, project: models.Project, question: str) -> list[dict]:
    """Vector search when possible, keyword search otherwise."""
    top_k = settings.chat.top_k
    if settings.ai_enabled and settings.qdrant.enabled:
        try:
            passages = vector_search(project, question, top_k)
        except (llm.LlmUnavailable, *vector_store.QDRANT_ERRORS):
            passages = []
        if passages:
            return passages
    return keyword_search(db, project, question, top_k)


def answer_errors(answer: LlmChatAnswer, passages: list[dict]) -> list[str]:
    """Problems that make the answer untrustworthy."""
    errors = []
    bad_numbers = [number for number in answer.passage_numbers if not 1 <= number <= len(passages)]
    if bad_numbers:
        errors.append(f"Passage numbers that do not exist: {bad_numbers}")
    facts = " ".join(passage["text"] for passage in passages)
    missing = grounding.unsupported_numbers(answer.answer, facts)
    if missing:
        errors.append(f"Numbers not found in the passages: {missing}")
    return errors


def ask_llm(question: str, passages: list[dict]) -> LlmChatAnswer | None:
    """LLM answer that passed the checks (one retry), or None."""
    context = prompts.numbered_passages([passage["text"] for passage in passages])
    errors: list[str] = []
    for _attempt in range(2):
        user_prompt = f"Passages:\n{context}\n\nQuestion: {question}"
        if errors:
            user_prompt += "\n\n" + prompts.CHAT_RETRY.format(errors="\n".join(errors))
        try:
            answer = llm.chat_json(prompts.CHAT_SYSTEM, user_prompt, LlmChatAnswer)
        except llm.LlmBadOutput as error:
            errors = [str(error)]
            continue
        errors = answer_errors(answer, passages)
        if not errors:
            return answer
    return None


def to_sources(passages: list[dict]) -> list[ChatSource]:
    """Passages as API sources."""
    return [ChatSource(document_id=passage["document_id"], filename=passage["filename"],
                       chunk_index=passage["chunk_index"], text=passage["text"]) for passage in passages]


def answer_question(db: Session, project: models.Project, question: str) -> ChatResponse:
    """Find passages and answer the question with the LLM or the template."""
    passages = find_passages(db, project, question)
    if not passages:
        return ChatResponse(answer=NO_PASSAGES, sources=[], method="template")
    if not settings.ai_enabled:
        return ChatResponse(answer=TEMPLATE_AI_OFF, sources=to_sources(passages), method="template")
    try:
        answer = ask_llm(question, passages)
    except llm.LlmUnavailable:
        answer = None
    if answer is None:
        return ChatResponse(answer=TEMPLATE_UNCHECKED, sources=to_sources(passages), method="template")
    used = [passages[number - 1] for number in sorted(set(answer.passage_numbers))]
    return ChatResponse(answer=answer.answer, sources=to_sources(used), method="llm")
