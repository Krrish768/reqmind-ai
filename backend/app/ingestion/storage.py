"""Keep uploaded files in the S3 store (Silo/MinIO from docker-compose.yml).

Example (needs the store running: docker compose up -d):
    python -m backend.app.ingestion.storage
"""
import io
from functools import lru_cache

import urllib3
from minio import Minio
from minio.error import S3Error

from backend.app.config import settings

# What a storage call can raise when the store is down or refuses the request
STORAGE_ERRORS = (S3Error, urllib3.exceptions.HTTPError, OSError)


@lru_cache(maxsize=1)
def get_client() -> Minio:
    """One shared S3 client."""
    http_client = urllib3.PoolManager(timeout=urllib3.Timeout(connect=3, read=30), retries=False)
    return Minio(settings.minio.endpoint, access_key=settings.minio.access_key,
                 secret_key=settings.minio.secret_key, secure=settings.minio.secure, http_client=http_client)


def ensure_bucket() -> None:
    """Create the bucket on first use."""
    client = get_client()
    if not client.bucket_exists(settings.minio.bucket):
        client.make_bucket(settings.minio.bucket)


def save_file(key: str, data: bytes, content_type: str) -> None:
    """Store the file bytes under the key."""
    ensure_bucket()
    get_client().put_object(settings.minio.bucket, key, io.BytesIO(data), length=len(data), content_type=content_type)


def read_file(key: str) -> bytes:
    """Return the stored bytes of one file."""
    response = get_client().get_object(settings.minio.bucket, key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def delete_file(key: str) -> None:
    """Remove one file (no error if it is already gone)."""
    get_client().remove_object(settings.minio.bucket, key)


if __name__ == "__main__":
    save_file("check/hello.txt", b"hello", "text/plain")
    print(read_file("check/hello.txt"))
    delete_file("check/hello.txt")
    print(f"Storage at {settings.minio.endpoint}, bucket {settings.minio.bucket}: ok")
