"""Load settings from configs/<APP_CONFIG>.yaml and secrets from .env.

Only the config file changes between machines, never the code.

Example:
    APP_CONFIG=cpu_laptop python -m backend.app.config
"""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "configs"
FRONTEND_DIR = REPO_ROOT / "frontend"
DEFAULT_CONFIG = "gpu_laptop"


class OllamaSettings(BaseModel):
    host: str
    llm_model: str
    embed_model: str
    num_ctx: int
    timeout_seconds: int
    keep_alive: str


class RedisSettings(BaseModel):
    enabled: bool
    url: str
    queue_name: str


class QdrantSettings(BaseModel):
    enabled: bool
    url: str
    collection: str


class Neo4jSettings(BaseModel):
    enabled: bool
    uri: str
    user: str
    password: str = ""


class MinioSettings(BaseModel):
    endpoint: str
    bucket: str
    secure: bool
    access_key: str = ""
    secret_key: str = ""


class IngestionSettings(BaseModel):
    max_upload_mb: int
    chunk_chars: int
    overlap_chars: int


class AnalysisSettings(BaseModel):
    max_chunks: int
    conflict_similarity: float
    max_conflict_pairs: int
    job_timeout_seconds: int


class ChatSettings(BaseModel):
    top_k: int


class Settings(BaseModel):
    config_name: str
    database_url: str
    jwt_secret_key: str
    ai_enabled: bool
    seed: int
    cors_origins: list[str]
    ollama: OllamaSettings
    redis: RedisSettings
    qdrant: QdrantSettings
    neo4j: Neo4jSettings
    minio: MinioSettings
    ingestion: IngestionSettings
    analysis: AnalysisSettings
    chat: ChatSettings


def _required_env(name: str) -> str:
    """Read an environment variable or stop with a clear message."""
    value = os.getenv(name, "")
    if not value:
        raise RuntimeError(f"{name} is not set. Copy .env.example to .env in the repo root and fill it.")
    return value


def load_config(config_name: str | None = None) -> Settings:
    """Read the YAML config for this machine and add the secrets from .env.

    Args:
        config_name: File name in configs/ without .yaml. Defaults to $APP_CONFIG.

    Returns:
        The validated settings.
    """
    load_dotenv(REPO_ROOT / ".env")
    name = config_name or os.getenv("APP_CONFIG", DEFAULT_CONFIG)
    config_path = CONFIG_DIR / f"{name}.yaml"
    if not config_path.exists():
        raise RuntimeError(f"Config {config_path} not found. Set APP_CONFIG to a file name in configs/.")

    raw = yaml.safe_load(config_path.read_text())
    raw["config_name"] = name
    raw["database_url"] = _required_env("DATABASE_URL")
    raw["jwt_secret_key"] = _required_env("JWT_SECRET_KEY")
    raw["neo4j"]["password"] = os.getenv("NEO4J_PASSWORD", "")
    raw["minio"]["access_key"] = os.getenv("MINIO_ACCESS_KEY", "")
    raw["minio"]["secret_key"] = os.getenv("MINIO_SECRET_KEY", "")
    return Settings.model_validate(raw)


settings = load_config()


if __name__ == "__main__":
    print(f"Config: {settings.config_name}  AI enabled: {settings.ai_enabled}")
    print(f"LLM: {settings.ollama.llm_model}  Embeddings: {settings.ollama.embed_model}")
    print(f"Redis: {settings.redis.enabled}  Qdrant: {settings.qdrant.enabled}  Neo4j: {settings.neo4j.enabled}")
