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

    # Databricks
    DATABRICKS_HOST: str = ""
    DATABRICKS_TOKEN: str = ""
    DATABRICKS_HTTP_PATH: str = ""
    DATABRICKS_CATALOG: str = "pharma_gold"
    DATABRICKS_SCHEMA: str = "gold"

    # Genie
    GENIE_ENABLED: bool = True
    GENIE_SPACE_ID: str = ""

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Redis (optional)
    REDIS_URL: str = "redis://localhost:6379"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
