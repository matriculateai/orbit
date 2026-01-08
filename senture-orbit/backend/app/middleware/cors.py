"""CORS middleware configuration."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings

logger = logging.getLogger(__name__)


def setup_cors(app: FastAPI, settings: Settings) -> None:
    """Configure CORS middleware for the application.

    In Databricks Apps, additional origins are automatically added
    for the workspace domain.

    Args:
        app: FastAPI application instance
        settings: Application settings
    """
    # Get CORS origins including Databricks Apps domains
    origins = settings.get_cors_origins()

    logger.info(f"Configuring CORS with origins: {origins}")
    logger.info(f"Auth mode: {'workspace' if settings.use_workspace_auth else 'token'}")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
