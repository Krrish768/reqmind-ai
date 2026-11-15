"""Store chunk vectors in Qdrant and search them, always limited to one project.

Set qdrant.url to ":memory:" to run without a Qdrant server (used by the tests).

Example:
    python -m backend.app.rag.vector_store
"""
from functools import lru_cache

import httpx
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from qdrant_client.http.exceptions import ApiException

from backend.app.config import settings

# What a Qdrant call can raise when the server is down or answers badly
QDRANT_ERRORS = (ApiException, httpx.HTTPError, OSError)


@lru_cache(maxsize=1)
def get_qdrant() -> QdrantClient:
    """One shared Qdrant client (in memory when the url is ":memory:")."""
    if settings.qdrant.url == ":memory:":
        return QdrantClient(location=":memory:")
    return QdrantClient(url=settings.qdrant.url, timeout=10, check_compatibility=False)


def ensure_collection(vector_size: int) -> None:
    """Create the collection (cosine distance) if it does not exist yet."""
    client = get_qdrant()
    if client.collection_exists(settings.qdrant.collection):
        return
    client.create_collection(
        collection_name=settings.qdrant.collection,
        vectors_config=qm.VectorParams(size=vector_size, distance=qm.Distance.COSINE),
    )


def _match(field: str, value: int) -> qm.FieldCondition:
    """Filter condition field == value."""
    return qm.FieldCondition(key=field, match=qm.MatchValue(value=value))


def delete_document(document_id: int) -> None:
    """Remove all vectors of one document (before indexing it again)."""
    client = get_qdrant()
    if not client.collection_exists(settings.qdrant.collection):
        return
    client.delete(
        collection_name=settings.qdrant.collection,
        points_selector=qm.FilterSelector(filter=qm.Filter(must=[_match("document_id", document_id)])),
    )


def index_chunks(payloads: list[dict], vectors: list[list[float]]) -> None:
    """Save chunk vectors. Each payload needs chunk_id, document_id, project_id and company_id.

    Args:
        payloads: One dict per chunk, stored next to its vector.
        vectors: One vector per chunk, same order.
    """
    if not vectors:
        return
    ensure_collection(len(vectors[0]))
    points = [qm.PointStruct(id=payload["chunk_id"], vector=vector, payload=payload)
              for payload, vector in zip(payloads, vectors)]
    get_qdrant().upsert(collection_name=settings.qdrant.collection, points=points)


def search(company_id: int, project_id: int, vector: list[float], top_k: int) -> list[dict]:
    """Closest chunks inside one project of one company.

    Returns:
        Payload dicts with an added "score" key, best first.
    """
    client = get_qdrant()
    if not client.collection_exists(settings.qdrant.collection):
        return []
    result = client.query_points(
        collection_name=settings.qdrant.collection,
        query=vector,
        query_filter=qm.Filter(must=[_match("company_id", company_id), _match("project_id", project_id)]),
        limit=top_k,
        with_payload=True,
    )
    return [{**point.payload, "score": point.score} for point in result.points]


if __name__ == "__main__":
    print(f"Qdrant at {settings.qdrant.url}: collections = {get_qdrant().get_collections()}")
