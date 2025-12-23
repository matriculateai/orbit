"""Application configuration using Pydantic settings."""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    APP_NAME: str = "Senture Orbit API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Supabase PostgreSQL
    POSTGRES_HOST: str = ""
    POSTGRES_PORT: int = 6543  # Use pooler port (6543) not direct port (5432)
    POSTGRES_DB: str = "postgres"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = ""
    POSTGRES_POOL_MIN_SIZE: int = 5
    POSTGRES_POOL_MAX_SIZE: int = 20
    POSTGRES_COMMAND_TIMEOUT: int = 30  # seconds
    POSTGRES_SSL_MODE: str = "require"  # Supabase requires SSL

    # Redis Cache
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    REDIS_CACHE_TTL: int = 3600  # 1 hour default cache TTL

    # Qdrant Vector DB (for RAG - query history)
    # For local Qdrant: set QDRANT_HOST and QDRANT_PORT
    # For Qdrant Cloud: set QDRANT_URL and QDRANT_API_KEY
    QDRANT_URL: str = ""  # e.g., "https://xyz-example.us-east.aws.cloud.qdrant.io"
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_API_KEY: str = ""
    QDRANT_COLLECTION: str = "query_history"
    QDRANT_VECTOR_SIZE: int = 384  # for all-MiniLM-L6-v2 embeddings

    # Claude AI (Anthropic)
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_HAIKU_MODEL: str = "claude-3-5-haiku-20241022"  # For simple queries
    CLAUDE_SONNET_MODEL: str = "claude-sonnet-4-20250514"  # For complex queries
    CLAUDE_MAX_TOKENS: int = 4096

    # Query Processing
    QUERY_COMPLEXITY_THRESHOLD: float = 0.6  # Route to Sonnet if complexity > 0.6
    RAG_TOP_K: int = 3  # Retrieve top 3 similar past queries for RAG
    ENABLE_QUERY_CACHING: bool = True

    # SQL Security
    SQL_MAX_QUERY_LENGTH: int = 50000  # Maximum SQL query length (prevent DoS)
    SQL_MAX_RESULT_ROWS: int = 10000  # Maximum rows returned per query
    SQL_ENABLE_VALIDATION: bool = True  # Enable SQL validation (always True in production)
    SQL_ALLOWED_SCHEMAS: List[str] = ["dim", "fact", "agg", "information_schema"]

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
