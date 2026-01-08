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


def sanitize_error(error: Exception, debug: bool = False) -> str:
    """Sanitize error messages to prevent information leakage.

    Args:
        error: The exception to sanitize
        debug: If True, include full error details

    Returns:
        Sanitized error message
    """
    if debug:
        return str(error)

    # In production, return generic messages without internal details
    error_str = str(error).lower()

    if "connection" in error_str or "timeout" in error_str:
        return "Connection failed"
    elif "auth" in error_str or "token" in error_str or "permission" in error_str:
        return "Authentication failed"
    elif "not found" in error_str:
        return "Resource not found"
    else:
        return "Service unavailable"


@router.get("/ping")
async def ping() -> Dict[str, str]:
    """Simple ping endpoint - no dependencies."""
    return {"status": "pong"}


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
        # Only include safe fields in response
        details["databricks"] = {
            "connected": databricks_connected,
            "auth_mode": db_status.get("auth_mode", "unknown"),
        }
        db_service.close()
    except Exception as e:
        logger.error(f"Databricks health check failed: {e}")
        details["databricks"] = {
            "connected": False,
            "error": sanitize_error(e, settings.DEBUG),
        }

    # Check Genie availability
    genie_available = False
    if settings.GENIE_ENABLED:
        try:
            genie_client = GenieClient(settings)
            genie_status = await genie_client.test_connection()
            genie_available = genie_status.get("available", False)
            # Only include safe fields in response
            details["genie"] = {
                "available": genie_available,
                "space_configured": genie_status.get("space_configured", False),
                "auth_mode": genie_status.get("auth_mode", "unknown"),
            }
            await genie_client.close()
        except Exception as e:
            logger.error(f"Genie health check failed: {e}")
            details["genie"] = {
                "available": False,
                "error": sanitize_error(e, settings.DEBUG),
            }
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
        # Return only safe fields
        return {
            "connected": status.get("connected", False),
            "auth_mode": status.get("auth_mode", "unknown"),
        }
    except Exception as e:
        logger.error(f"Databricks health check failed: {e}")
        return {
            "connected": False,
            "error": sanitize_error(e, settings.DEBUG),
        }


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
        # Return only safe fields
        return {
            "available": status.get("available", False),
            "space_configured": status.get("space_configured", False),
            "auth_mode": status.get("auth_mode", "unknown"),
        }
    except Exception as e:
        logger.error(f"Genie health check failed: {e}")
        return {
            "available": False,
            "error": sanitize_error(e, settings.DEBUG),
        }
