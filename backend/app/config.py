import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Core
    DATABASE_URL = os.getenv("DATABASE_URL")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")

    # AI switch: "true" only on Krrish's machine (Ollama). Muskaan keeps "false" -> AI endpoints return mock data.
    AI_ENABLED = os.getenv("AI_ENABLED", "false").lower() == "true"

    # MinIO (file storage) - Muskaan
    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "reqmind_minio")
    MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "reqmind_minio_pass")
    MINIO_BUCKET = os.getenv("MINIO_BUCKET", "reqmind-documents")
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))

    # AI stack - Krrish
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "qwen3:8b")
    OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    OLLAMA_NUM_CTX = int(os.getenv("OLLAMA_NUM_CTX", "8192"))
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
    QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "reqmind_chunks")
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "reqmind_neo4j_pass")
    MAX_CHUNKS_PER_ANALYSIS = int(os.getenv("MAX_CHUNKS_PER_ANALYSIS", "40"))


settings = Settings()
