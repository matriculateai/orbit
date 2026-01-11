"""CORS middleware configuration."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings

logger = logging.getLogger(__name__)


def setup_cors(app: FastAPI, settings: Settings) -> None:
    """Configure CORS middleware for the application.

    In Databricks Apps, the frontend is served from the same origin as the API,
    so CORS is less of a concern. For local development, we allow localhost.

    Args:
        app: FastAPI application instance
        settings: Application settings
    """
    origins = list(settings.CORS_ORIGINS)

    logger.info(f"Configuring CORS with origins: {origins}")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
