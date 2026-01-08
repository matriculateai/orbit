"""Application configuration using Pydantic settings."""
import os
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


def is_databricks_apps_environment() -> bool:
    """Detect if running within Databricks Apps environment.

    Databricks Apps sets specific environment variables that we can use
    to detect the runtime environment.
    """
    # Check for Databricks Apps specific environment variables
    return any([
        os.getenv("DATABRICKS_RUNTIME_VERSION"),
        os.getenv("DB_IS_DRIVER"),
        os.getenv("DATABRICKS_APP_ID"),
        os.getenv("IS_DATABRICKS_APPS", "").lower() == "true",
    ])


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

    # Databricks Apps detection
    IS_DATABRICKS_APPS: bool = False

    # Databricks - Host and Token are optional when using workspace auth in Databricks Apps
    DATABRICKS_HOST: Optional[str] = None
    DATABRICKS_TOKEN: Optional[str] = None
    DATABRICKS_HTTP_PATH: Optional[str] = None
    DATABRICKS_CATALOG: str = "pharma_gold"
    DATABRICKS_SCHEMA: str = "gold"

    # SQL Warehouse configuration for Databricks Apps
    DATABRICKS_WAREHOUSE_ID: Optional[str] = None

    # Genie
    GENIE_ENABLED: bool = True
    GENIE_SPACE_ID: str = ""

    # Claude AI (Anthropic)
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    CLAUDE_MAX_TOKENS: int = 4096

    # CORS - Extended for Databricks Apps
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # Redis (optional)
    REDIS_URL: str = "redis://localhost:6379"

    # Static files path for serving frontend in Databricks Apps
    STATIC_FILES_PATH: str = "/app/static"

    @property
    def use_workspace_auth(self) -> bool:
        """Determine if workspace authentication should be used.

        In Databricks Apps, workspace authentication is automatic and preferred.
        When running locally, explicit host/token configuration is required.
        """
        return is_databricks_apps_environment() or self.IS_DATABRICKS_APPS

    @property
    def effective_databricks_host(self) -> Optional[str]:
        """Get the effective Databricks host.

        In Databricks Apps, this may be auto-detected from environment.
        """
        if self.DATABRICKS_HOST:
            return self.DATABRICKS_HOST
        # In Databricks Apps, the host can be inferred from workspace context
        return os.getenv("DATABRICKS_HOST") or os.getenv("DB_WORKSPACE_HOST")

    def get_cors_origins(self) -> List[str]:
        """Get CORS origins including Databricks Apps domains."""
        origins = list(self.CORS_ORIGINS)

        # Add Databricks Apps domains when running in that environment
        if self.use_workspace_auth:
            host = self.effective_databricks_host
            if host:
                # Add the workspace domain for Databricks Apps
                origins.append(host)
                # Add common Databricks Apps URL patterns
                if "cloud.databricks.com" in host:
                    origins.append("https://*.cloud.databricks.com")
                elif "azuredatabricks.net" in host:
                    origins.append("https://*.azuredatabricks.net")
                elif "gcp.databricks.com" in host:
                    origins.append("https://*.gcp.databricks.com")

        return origins


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
