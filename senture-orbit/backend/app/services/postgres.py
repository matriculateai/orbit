"""PostgreSQL service for Supabase connection."""
import asyncpg
import logging
import time
from typing import List, Dict, Any, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class PostgresService:
    """
    PostgreSQL service for Supabase connection with connection pooling.

    This service replaces DatabricksService and provides:
    - Async connection pooling via asyncpg
    - Retry logic for transient failures
    - Query logging and timing
    - Health check functionality
    """

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self._connection_string = self._build_connection_string()

    def _build_connection_string(self) -> str:
        """Build PostgreSQL connection string from settings."""
        return (
            f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
            f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}"
            f"/{settings.POSTGRES_DB}"
        )

    async def connect(self):
        """
        Initialize connection pool to Supabase PostgreSQL.

        Uses connection pooler (port 6543) for production workloads.
        """
        if self.pool is not None:
            logger.warning("Connection pool already exists")
            return

        try:
            self.pool = await asyncpg.create_pool(
                host=settings.POSTGRES_HOST,
                port=settings.POSTGRES_PORT,
                user=settings.POSTGRES_USER,
                password=settings.POSTGRES_PASSWORD,
                database=settings.POSTGRES_DB,
                min_size=settings.POSTGRES_POOL_MIN_SIZE,
                max_size=settings.POSTGRES_POOL_MAX_SIZE,
                command_timeout=settings.POSTGRES_COMMAND_TIMEOUT,
                ssl=settings.POSTGRES_SSL_MODE,
                # Additional connection parameters
                server_settings={
                    'application_name': settings.APP_NAME,
                    'jit': 'off',  # Disable JIT for faster query planning
                }
            )
            logger.info(
                f"PostgreSQL connection pool created "
                f"(min={settings.POSTGRES_POOL_MIN_SIZE}, "
                f"max={settings.POSTGRES_POOL_MAX_SIZE})"
            )

            # Test connection
            await self.health_check()

        except Exception as e:
            logger.error(f"Failed to create PostgreSQL connection pool: {e}")
            raise

    async def disconnect(self):
        """Close connection pool gracefully."""
        if self.pool:
            await self.pool.close()
            logger.info("PostgreSQL connection pool closed")
            self.pool = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((
            asyncpg.PostgresConnectionError,
            asyncpg.InterfaceError,
        )),
        reraise=True,
    )
    async def execute_query(
        self,
        query: str,
        params: Optional[List[Any]] = None,
        fetch_all: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Execute SQL query and return results as list of dicts.

        Args:
            query: SQL SELECT statement
            params: Optional query parameters (for parameterized queries)
            fetch_all: If True, fetch all rows; if False, fetch one row

        Returns:
            List of dictionaries representing rows

        Raises:
            asyncpg.PostgresError: On database errors
            RuntimeError: If connection pool not initialized
        """
        if self.pool is None:
            raise RuntimeError(
                "PostgreSQL connection pool not initialized. "
                "Call connect() first."
            )

        start_time = time.time()

        try:
            async with self.pool.acquire() as conn:
                if fetch_all:
                    rows = await conn.fetch(query, *(params or []))
                else:
                    row = await conn.fetchrow(query, *(params or []))
                    rows = [row] if row else []

                # Convert asyncpg.Record to dict
                result = [dict(row) for row in rows]

                execution_time = time.time() - start_time
                logger.info(
                    f"Query executed in {execution_time:.3f}s, "
                    f"returned {len(result)} rows"
                )

                # Log slow queries (> 2 seconds)
                if execution_time > 2.0:
                    logger.warning(
                        f"Slow query detected ({execution_time:.3f}s): "
                        f"{query[:200]}..."
                    )

                return result

        except asyncpg.PostgresSyntaxError as e:
            logger.error(f"SQL syntax error: {e}\nQuery: {query}")
            raise
        except asyncpg.PostgresError as e:
            logger.error(f"PostgreSQL error: {e}\nQuery: {query}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error executing query: {e}\nQuery: {query}")
            raise

    async def execute_query_batch(
        self,
        queries: List[str]
    ) -> List[List[Dict[str, Any]]]:
        """
        Execute multiple queries in a single transaction.

        Args:
            queries: List of SQL queries to execute

        Returns:
            List of results (one per query)
        """
        if self.pool is None:
            raise RuntimeError("PostgreSQL connection pool not initialized")

        results = []
        start_time = time.time()

        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    for query in queries:
                        rows = await conn.fetch(query)
                        results.append([dict(row) for row in rows])

            execution_time = time.time() - start_time
            logger.info(
                f"Batch query ({len(queries)} queries) executed in "
                f"{execution_time:.3f}s"
            )

            return results

        except asyncpg.PostgresError as e:
            logger.error(f"PostgreSQL batch query error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error in batch query: {e}")
            raise

    async def health_check(self) -> bool:
        """
        Check database connection health.

        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            if self.pool is None:
                logger.error("Health check failed: Connection pool not initialized")
                return False

            # Simple query to test connection
            result = await self.execute_query("SELECT 1 as health_check")

            if result and result[0].get('health_check') == 1:
                logger.debug("PostgreSQL health check passed")
                return True
            else:
                logger.error("Health check returned unexpected result")
                return False

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def get_table_info(self, schema: str, table: str) -> Dict[str, Any]:
        """
        Get table metadata (columns, types, etc.).

        Args:
            schema: Schema name (e.g., 'dim', 'fact', 'agg')
            table: Table name

        Returns:
            Dictionary with table metadata
        """
        query = """
        SELECT
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema = $1 AND table_name = $2
        ORDER BY ordinal_position
        """

        columns = await self.execute_query(query, params=[schema, table])

        return {
            "schema": schema,
            "table": table,
            "columns": columns,
            "column_count": len(columns),
        }

    async def get_table_row_count(self, schema: str, table: str) -> int:
        """
        Get approximate row count for a table.

        Args:
            schema: Schema name
            table: Table name

        Returns:
            Approximate row count
        """
        query = f"SELECT COUNT(*) as count FROM {schema}.{table}"
        result = await self.execute_query(query, fetch_all=False)
        return result[0]['count'] if result else 0

    async def get_pool_stats(self) -> Dict[str, Any]:
        """
        Get connection pool statistics.

        Returns:
            Dictionary with pool stats
        """
        if self.pool is None:
            return {"status": "not_initialized"}

        return {
            "status": "active",
            "size": self.pool.get_size(),
            "free_size": self.pool.get_idle_size(),
            "min_size": self.pool.get_min_size(),
            "max_size": self.pool.get_max_size(),
        }
