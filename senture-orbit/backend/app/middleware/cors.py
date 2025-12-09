"""CORS middleware configuration."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings


def setup_cors(app: FastAPI, settings: Settings) -> None:
    """Configure CORS middleware for the application.

    Args:
        app: FastAPI application instance
        settings: Application settings
    """
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )
