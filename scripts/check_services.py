"""Check every service this machine's config needs and print one line each.

Exits with code 1 if a needed service is not reachable.

Example (from the repo root):
    python -m scripts.check_services
"""
import argparse
import socket
import sys
from collections.abc import Callable

from rq import Worker
from sqlalchemy import text

from backend.app.config import settings
from backend.app.database import engine
from backend.app.jobs import get_queue
from backend.app.knowledge_graph.neo4j_store import get_driver
from backend.app.llm.client import ollama_status
from backend.app.rag.vector_store import get_qdrant


def check_postgres() -> str:
    """Run SELECT 1."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return "ok"


def check_redis() -> str:
    """Ping Redis and count running workers."""
    queue = get_queue()
    queue.connection.ping()
    workers = Worker.count(connection=queue.connection)
    return "ok" if workers else "ok, but no worker running. Start one: python -m scripts.run_worker"


def check_qdrant() -> str:
    """List collections."""
    get_qdrant().get_collections()
    return "ok"


def check_neo4j() -> str:
    """Open a connection."""
    get_driver().verify_connectivity()
    return "ok"


def check_minio() -> str:
    """Open a TCP connection to the MinIO port."""
    host, port = settings.minio.endpoint.split(":")
    with socket.create_connection((host, int(port)), timeout=3):
        return "ok"


def run_check(name: str, needed: bool, check: Callable[[], str]) -> bool:
    """Run one check, print the result, return False only if a needed service failed."""
    if not needed:
        print(f"{name:<10} off in configs/{settings.config_name}.yaml")
        return True
    try:
        result = check()
    except Exception as error:  # report any failure and keep checking the rest
        result = f"FAILED: {type(error).__name__}: {error}"
    print(f"{name:<10} {result}")
    return result.startswith("ok")


def main() -> None:
    argparse.ArgumentParser(description="Check the services needed by this machine's config.").parse_args()
    print(f"Config: {settings.config_name}  (AI {'on' if settings.ai_enabled else 'off'})")
    results = [
        run_check("postgres", True, check_postgres),
        run_check("minio", True, check_minio),
        run_check("redis", settings.redis.enabled, check_redis),
        run_check("qdrant", settings.qdrant.enabled, check_qdrant),
        run_check("neo4j", settings.neo4j.enabled, check_neo4j),
        run_check("ollama", settings.ai_enabled, ollama_status),
    ]
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
