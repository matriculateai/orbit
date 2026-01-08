"""Senture Orbit API - Pharmaceutical Commercial Intelligence Platform.

FastAPI application for pharmaceutical analytics with Databricks Genie integration.
Supports deployment as a Databricks App with workspace authentication.
"""
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

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
    logger.info(f"Databricks Host: {settings.effective_databricks_host}")
    logger.info(f"Auth Mode: {'workspace' if settings.use_workspace_auth else 'token'}")
    logger.info(f"Genie Enabled: {settings.GENIE_ENABLED}")

    if settings.use_workspace_auth:
        logger.info("Running in Databricks Apps mode with workspace authentication")
    else:
        logger.info("Running in local development mode with token authentication")

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

    # Serve static files for frontend in Databricks Apps
    static_path = Path(settings.STATIC_FILES_PATH).resolve()
    if static_path.exists() and static_path.is_dir():
        logger.info(f"Serving static files from: {static_path}")

        # Mount static assets (JS, CSS, images)
        static_assets = static_path / "static"
        if static_assets.exists():
            app.mount("/static", StaticFiles(directory=str(static_assets)), name="static")

        # Serve index.html for SPA routes
        @app.get("/{full_path:path}")
        async def serve_spa(request: Request, full_path: str) -> FileResponse:
            """Serve the React SPA for all non-API routes."""
            # Skip API routes and docs
            if full_path.startswith(("api/", "docs", "redoc", "openapi.json", "health")):
                return JSONResponse(
                    status_code=404,
                    content={"error": "Not found"}
                )

            # SECURITY: Prevent path traversal attacks
            # Resolve the full path and verify it's within the static directory
            try:
                # Normalize and resolve the requested path
                requested_path = (static_path / full_path).resolve()

                # Verify the resolved path is within the static directory
                # This prevents ../../../etc/passwd style attacks
                if not str(requested_path).startswith(str(static_path)):
                    logger.warning(f"Path traversal attempt blocked: {full_path}")
                    return JSONResponse(
                        status_code=403,
                        content={"error": "Forbidden"}
                    )

                # Serve the file if it exists and is a regular file
                if requested_path.exists() and requested_path.is_file():
                    return FileResponse(str(requested_path))

            except (ValueError, OSError) as e:
                # Invalid path (e.g., null bytes, invalid characters)
                logger.warning(f"Invalid path requested: {full_path}, error: {e}")
                return JSONResponse(
                    status_code=400,
                    content={"error": "Invalid path"}
                )

            # Otherwise serve index.html for SPA routing
            index_path = static_path / "index.html"
            if index_path.exists():
                return FileResponse(str(index_path))

            return JSONResponse(
                status_code=404,
                content={"error": "Not found"}
            )
    else:
        logger.info(f"Static files not found at {static_path}, running in API-only mode")

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
