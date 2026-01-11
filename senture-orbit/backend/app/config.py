"""Application configuration using Pydantic settings.

Note: Databricks authentication is handled by the SDK automatically.
The SDK uses the default credential provider chain which supports:
- Environment variables (DATABRICKS_HOST, DATABRICKS_TOKEN)
- Databricks CLI profiles (~/.databrickscfg)
- Azure/GCP/AWS native auth
- Workspace auth in Databricks Apps
"""
from functools import lru_cache
from typing import List, Optional

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

    # Databricks SQL Warehouse
    # Note: DATABRICKS_HOST and DATABRICKS_TOKEN are read directly by the SDK
    # from environment variables, so we don't need to define them here.
    DATABRICKS_HTTP_PATH: Optional[str] = None
    DATABRICKS_WAREHOUSE_ID: Optional[str] = None
    DATABRICKS_CATALOG: str = "pharma_gold"
    DATABRICKS_SCHEMA: str = "gold"

    # Genie
    GENIE_ENABLED: bool = True
    GENIE_SPACE_ID: str = ""

    # Claude AI (Anthropic)
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    CLAUDE_MAX_TOKENS: int = 4096

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Redis (optional)
    REDIS_URL: str = "redis://localhost:6379"

    # Static files path for serving frontend in Databricks Apps
    STATIC_FILES_PATH: str = "/app/static"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
