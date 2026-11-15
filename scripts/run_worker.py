"""Run the analysis worker. It takes jobs from the Redis queue one at a time.

Run from the repo root, in its own terminal, next to the API server:
    python -m scripts.run_worker
    python -m scripts.run_worker --burst   # finish the queued jobs, then stop
"""
import argparse

from redis.exceptions import RedisError
from rq import Worker

from backend.app.config import settings
from backend.app.jobs import get_queue


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ReqMind analysis worker.")
    parser.add_argument("--burst", action="store_true", help="stop when the queue is empty")
    args = parser.parse_args()

    if not settings.redis.enabled:
        print(f"Redis is off in configs/{settings.config_name}.yaml, so the API runs jobs itself. No worker needed.")
        return
    queue = get_queue()
    try:
        queue.connection.ping()
    except RedisError as error:
        print(f"Cannot reach Redis at {settings.redis.url}: {error}. Start it with: docker compose --profile ai up -d")
        return
    print(f"Worker listening on queue '{settings.redis.queue_name}' (config {settings.config_name})")
    Worker([queue], connection=queue.connection).work(burst=args.burst)


if __name__ == "__main__":
    main()
