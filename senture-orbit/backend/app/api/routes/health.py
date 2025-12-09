"""Health check endpoints."""
import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.models.responses import HealthResponse
from app.services.databricks import DatabricksService
from app.services.genie_client import GenieClient

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/", response_model=Dict[str, Any])
async def root(settings: Settings = Depends(get_settings)) -> Dict[str, Any]:
    """API root endpoint with basic information."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "health": "/health",
    }


@router.get("/health", response_model=HealthResponse)
async def health_check(
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """Comprehensive health check for all services.

    Checks:
    - Databricks SQL Warehouse connectivity
    - Genie API availability
    """
    details: Dict[str, Any] = {}

    # Check Databricks connection
    databricks_connected = False
    try:
        db_service = DatabricksService(settings)
        db_status = await db_service.test_connection()
        databricks_connected = db_status.get("connected", False)
        details["databricks"] = db_status
        db_service.close()
    except Exception as e:
        logger.error(f"Databricks health check failed: {e}")
        details["databricks"] = {"connected": False, "error": str(e)}

    # Check Genie availability
    genie_available = False
    if settings.GENIE_ENABLED:
        try:
            genie_client = GenieClient(settings)
            genie_status = await genie_client.test_connection()
            genie_available = genie_status.get("available", False)
            details["genie"] = genie_status
            await genie_client.close()
        except Exception as e:
            logger.error(f"Genie health check failed: {e}")
            details["genie"] = {"available": False, "error": str(e)}
    else:
        details["genie"] = {"available": False, "reason": "Genie is disabled"}

    # Determine overall status
    if databricks_connected and (genie_available or not settings.GENIE_ENABLED):
        status = "healthy"
    elif databricks_connected:
        status = "degraded"
    else:
        status = "unhealthy"

    return HealthResponse(
        status=status,
        databricks_connected=databricks_connected,
        genie_available=genie_available,
        version=settings.APP_VERSION,
        details=details,
    )


@router.get("/health/databricks")
async def databricks_health(
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    """Check Databricks SQL Warehouse connectivity."""
    try:
        db_service = DatabricksService(settings)
        status = await db_service.test_connection()
        db_service.close()
        return status
    except Exception as e:
        logger.error(f"Databricks health check failed: {e}")
        return {"connected": False, "error": str(e)}


@router.get("/health/genie")
async def genie_health(
    settings: Settings = Depends(get_settings),
) -> Dict[str, Any]:
    """Check Genie API availability."""
    if not settings.GENIE_ENABLED:
        return {"available": False, "reason": "Genie is disabled"}

    try:
        genie_client = GenieClient(settings)
        status = await genie_client.test_connection()
        await genie_client.close()
        return status
    except Exception as e:
        logger.error(f"Genie health check failed: {e}")
        return {"available": False, "error": str(e)}
