"""FastAPI dependency injection for services."""
import logging
from typing import Optional

from app.services.postgres import PostgresService
from app.services.redis_service import RedisService
from app.services.qdrant_service import QdrantService
from app.services.claude_service import ClaudeService

logger = logging.getLogger(__name__)

# Global singleton instances (initialized in lifespan)
_postgres: Optional[PostgresService] = None
_redis: Optional[RedisService] = None
_qdrant: Optional[QdrantService] = None
_claude: Optional[ClaudeService] = None


# ============================================================================
# Service Initialization (called from main.py lifespan)
# ============================================================================

async def initialize_services():
    """
    Initialize all services during application startup.

    Call this from the FastAPI lifespan context manager.
    """
    global _postgres, _redis, _qdrant, _claude

    logger.info("Initializing services...")

    # Initialize PostgreSQL
    try:
        _postgres = PostgresService()
        await _postgres.connect()
        logger.info("✓ PostgreSQL service initialized")
    except Exception as e:
        logger.error(f"✗ Failed to initialize PostgreSQL: {e}")
        raise

    # Initialize Redis (optional, don't fail if unavailable)
    try:
        _redis = RedisService()
        await _redis.connect()
        logger.info("✓ Redis service initialized")
    except Exception as e:
        logger.warning(f"⚠ Redis not available: {e}")
        _redis = None

    # Initialize Qdrant (optional, don't fail if unavailable)
    try:
        _qdrant = QdrantService()
        await _qdrant.connect()
        await _qdrant.initialize_collection()
        logger.info("✓ Qdrant service initialized")
    except Exception as e:
        logger.warning(f"⚠ Qdrant not available: {e}")
        _qdrant = None

    # Initialize Claude service (with Qdrant for RAG if available)
    try:
        _claude = ClaudeService(qdrant_service=_qdrant)
        logger.info("✓ Claude service initialized")
    except Exception as e:
        logger.error(f"✗ Failed to initialize Claude service: {e}")
        raise

    logger.info("All services initialized successfully")


async def shutdown_services():
    """
    Shutdown all services gracefully during application shutdown.

    Call this from the FastAPI lifespan context manager.
    """
    global _postgres, _redis, _qdrant, _claude

    logger.info("Shutting down services...")

    if _postgres:
        try:
            await _postgres.disconnect()
            logger.info("✓ PostgreSQL disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting PostgreSQL: {e}")

    if _redis:
        try:
            await _redis.disconnect()
            logger.info("✓ Redis disconnected")
        except Exception as e:
            logger.error(f"Error disconnecting Redis: {e}")

    # Qdrant and Claude don't need explicit shutdown
    _claude = None
    _qdrant = None

    logger.info("All services shut down")


# ============================================================================
# Dependency Injection Functions
# ============================================================================

async def get_postgres() -> PostgresService:
    """
    Get PostgreSQL service instance.

    Raises:
        RuntimeError: If service not initialized
    """
    if _postgres is None:
        raise RuntimeError(
            "PostgreSQL service not initialized. "
            "Ensure initialize_services() was called during startup."
        )
    return _postgres


async def get_redis() -> Optional[RedisService]:
    """
    Get Redis service instance.

    Returns:
        RedisService instance, or None if Redis is not available
    """
    return _redis


async def get_qdrant() -> Optional[QdrantService]:
    """
    Get Qdrant service instance.

    Returns:
        QdrantService instance, or None if Qdrant is not available
    """
    return _qdrant


async def get_claude() -> ClaudeService:
    """
    Get Claude service instance.

    Raises:
        RuntimeError: If service not initialized
    """
    if _claude is None:
        raise RuntimeError(
            "Claude service not initialized. "
            "Ensure initialize_services() was called during startup."
        )
    return _claude


# ============================================================================
# Service Health Checks
# ============================================================================

async def check_services_health() -> dict:
    """
    Check health of all services.

    Returns:
        Dictionary with health status of each service
    """
    health = {
        "postgres": False,
        "redis": False,
        "qdrant": False,
        "claude": False,
    }

    # Check PostgreSQL
    if _postgres:
        try:
            health["postgres"] = await _postgres.health_check()
        except Exception as e:
            logger.error(f"PostgreSQL health check failed: {e}")

    # Check Redis
    if _redis:
        try:
            health["redis"] = await _redis.health_check()
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")

    # Check Qdrant
    if _qdrant:
        try:
            health["qdrant"] = await _qdrant.health_check()
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")

    # Claude service is always available if initialized
    health["claude"] = _claude is not None

    return health
