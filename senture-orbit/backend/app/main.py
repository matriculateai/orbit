"""Senture Orbit API - Pharmaceutical Commercial Intelligence Platform.

FastAPI application for pharmaceutical analytics with Databricks Genie integration.
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import api_router
from app.config import get_settings
from app.middleware import setup_cors

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager for startup and shutdown events."""
    # Startup
    settings = get_settings()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Databricks Host: {settings.DATABRICKS_HOST}")
    logger.info(f"Genie Enabled: {settings.GENIE_ENABLED}")

    yield

    # Shutdown
    logger.info("Shutting down application")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Pharmaceutical Commercial Intelligence Platform with Databricks Genie AI",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Setup CORS
    setup_cors(app, settings)

    # Include API routes
    app.include_router(api_router)

    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Internal server error",
                "detail": str(exc) if settings.DEBUG else "An unexpected error occurred",
            },
        )

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
