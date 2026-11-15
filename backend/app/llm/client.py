"""Talk to the local Ollama server: JSON answers from the LLM and text embeddings.

Example:
    python -m backend.app.llm.client
"""
from functools import lru_cache

import httpx
import ollama
from pydantic import BaseModel, ValidationError

from backend.app.config import settings

# nomic-embed-text was trained with these task prefixes
DOCUMENT_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "


class LlmUnavailable(Exception):
    """Ollama could not be reached, or the model is missing."""


class LlmBadOutput(Exception):
    """The model answered, but the answer did not match the JSON schema."""


@lru_cache(maxsize=1)
def _client() -> ollama.Client:
    """One shared Ollama client."""
    return ollama.Client(host=settings.ollama.host, timeout=settings.ollama.timeout_seconds)


def chat_json(system_prompt: str, user_prompt: str, schema: type[BaseModel]) -> BaseModel:
    """Ask the LLM for an answer that follows a Pydantic schema.

    Temperature 0, a fixed seed and no hidden "thinking", so answers are
    repeatable and fast.

    Args:
        system_prompt: Rules for the model.
        user_prompt: The text and the question.
        schema: Pydantic model the answer must match.

    Returns:
        The parsed answer.

    Raises:
        LlmUnavailable: Ollama is down or the model is not pulled.
        LlmBadOutput: The answer was not valid for the schema.
    """
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
    options = {"temperature": 0, "seed": settings.seed, "num_ctx": settings.ollama.num_ctx}
    try:
        response = _client().chat(
            model=settings.ollama.llm_model,
            messages=messages,
            format=schema.model_json_schema(),
            think=False,
            options=options,
            keep_alive=settings.ollama.keep_alive,
        )
    except (ollama.ResponseError, httpx.HTTPError, ConnectionError) as error:
        raise LlmUnavailable(f"Ollama chat failed: {error}") from error
    try:
        return schema.model_validate_json(response.message.content)
    except ValidationError as error:
        raise LlmBadOutput(f"Answer did not match {schema.__name__}: {error.error_count()} errors") from error


def embed_texts(texts: list[str], is_query: bool = False) -> list[list[float]]:
    """Turn texts into vectors with the embedding model.

    Args:
        texts: Texts to embed.
        is_query: True for a search question, False for document text.

    Returns:
        One vector per text, in the same order.

    Raises:
        LlmUnavailable: Ollama is down or the model is not pulled.
    """
    if not texts:
        return []
    prefix = QUERY_PREFIX if is_query else DOCUMENT_PREFIX
    try:
        response = _client().embed(
            model=settings.ollama.embed_model,
            input=[prefix + text for text in texts],
            keep_alive=settings.ollama.keep_alive,
        )
    except (ollama.ResponseError, httpx.HTTPError, ConnectionError) as error:
        raise LlmUnavailable(f"Ollama embed failed: {error}") from error
    return [list(vector) for vector in response.embeddings]


def ollama_status() -> str:
    """Return "ok" when both models are pulled, else the reason."""
    try:
        listed = _client().list()
    except (ollama.ResponseError, httpx.HTTPError, ConnectionError) as error:
        return f"not reachable at {settings.ollama.host}: {error}"
    names = {model.model for model in listed.models}
    missing = [name for name in (settings.ollama.llm_model, settings.ollama.embed_model)
               if name not in names and f"{name}:latest" not in names]
    if missing:
        return f"missing models {missing}. Run: python -m scripts.download_weights"
    return "ok"


if __name__ == "__main__":
    print(f"Ollama: {ollama_status()}")
    vectors = embed_texts(["The system shall log every payment."])
    print(f"Embedding size: {len(vectors[0])}")
