"""Health check endpoints."""
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.models.responses import HealthResponse
from app.dependencies import check_services_health, get_postgres, get_redis, get_qdrant, get_claude
from app.services.postgres import PostgresService
from app.services.redis_service import RedisService
from app.services.qdrant_service import QdrantService
from app.services.claude_service import ClaudeService

router = APIRouter()
logger = logging.getLogger(__name__)


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
        "stack": "Supabase PostgreSQL + Claude AI (Haiku/Sonnet)",
    }


@router.get("/health", response_model=HealthResponse)
async def health_check(
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    """
    Comprehensive health check for all services.

    Checks:
    - PostgreSQL (Supabase) connectivity
    - Redis cache availability
    - Qdrant vector DB availability
    - Claude AI service availability
    """
    # Get health status for all services
    health_status = await check_services_health()

    postgres_connected = health_status.get("postgres", False)
    redis_available = health_status.get("redis", False)
    qdrant_available = health_status.get("qdrant", False)
    claude_available = health_status.get("claude", False)

    # Build detailed status
    details: Dict[str, Any] = {
        "postgres": {
            "connected": postgres_connected,
            "service": "Supabase PostgreSQL",
        },
        "redis": {
            "available": redis_available,
            "service": "Redis Cache",
        },
        "qdrant": {
            "available": qdrant_available,
            "service": "Qdrant Vector DB (RAG)",
        },
        "claude": {
            "available": claude_available,
            "service": "Claude AI (Haiku/Sonnet)",
        },
    }

    # Determine overall status
    # PostgreSQL and Claude are critical, Redis and Qdrant are optional
    if postgres_connected and claude_available:
        if redis_available and qdrant_available:
            status = "healthy"
        else:
            status = "degraded"
    else:
        status = "unhealthy"

    return HealthResponse(
        status=status,
        postgres_connected=postgres_connected,
        redis_available=redis_available,
        qdrant_available=qdrant_available,
        claude_available=claude_available,
        version=settings.APP_VERSION,
        details=details,
    )


@router.get("/health/postgres")
async def postgres_health(
    postgres: PostgresService = Depends(get_postgres),
) -> Dict[str, Any]:
    """Check PostgreSQL (Supabase) connectivity."""
    try:
        is_healthy = await postgres.health_check()
        pool_stats = await postgres.get_pool_stats()

        return {
            "connected": is_healthy,
            "service": "Supabase PostgreSQL",
            "pool": pool_stats,
        }
    except Exception as e:
        logger.error(f"PostgreSQL health check failed: {e}")
        return {
            "connected": False,
            "error": str(e),
        }


@router.get("/health/redis")
async def redis_health(
    redis: Optional[RedisService] = Depends(get_redis),
) -> Dict[str, Any]:
    """Check Redis cache availability."""
    if redis is None:
        return {
            "available": False,
            "reason": "Redis service not initialized",
        }

    try:
        is_healthy = await redis.health_check()
        stats = await redis.get_cache_stats()

        return {
            "available": is_healthy,
            "service": "Redis Cache",
            "stats": stats,
        }
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {
            "available": False,
            "error": str(e),
        }


@router.get("/health/qdrant")
async def qdrant_health(
    qdrant: Optional[QdrantService] = Depends(get_qdrant),
) -> Dict[str, Any]:
    """Check Qdrant vector DB availability."""
    if qdrant is None:
        return {
            "available": False,
            "reason": "Qdrant service not initialized",
        }

    try:
        is_healthy = await qdrant.health_check()
        stats = await qdrant.get_collection_stats()

        return {
            "available": is_healthy,
            "service": "Qdrant Vector DB (RAG)",
            "stats": stats,
        }
    except Exception as e:
        logger.error(f"Qdrant health check failed: {e}")
        return {
            "available": False,
            "error": str(e),
        }


@router.get("/health/claude")
async def claude_health(
    claude: ClaudeService = Depends(get_claude),
) -> Dict[str, Any]:
    """Check Claude AI service availability."""
    try:
        # Claude service is available if dependency injection succeeds
        return {
            "available": claude is not None,
            "service": "Claude AI (Haiku/Sonnet)",
            "models": {
                "haiku": "claude-haiku-4.5-20251022",
                "sonnet": "claude-sonnet-4-20250514",
            },
        }
    except Exception as e:
        logger.error(f"Claude health check failed: {e}")
        return {
            "available": False,
            "error": str(e),
        }
