"""PostgreSQL service for Supabase connection."""
import asyncpg
import logging
import time
from decimal import Decimal
from typing import List, Dict, Any, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from app.config import get_settings
from app.security import (
    validate_query,
    validate_schema,
    validate_table_name,
    SQLValidationError,
)

logger = logging.getLogger(__name__)
settings = get_settings()


def _convert_record_to_dict(record: asyncpg.Record) -> Dict[str, Any]:
    """
    Convert asyncpg.Record to dict with JSON-serializable values.

    Converts Decimal objects to float for JSON serialization.
    """
    result = {}
    for key, value in record.items():
        if isinstance(value, Decimal):
            result[key] = float(value)
        else:
            result[key] = value
    return result


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
        skip_validation: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Execute SQL query and return results as list of dicts.

        SECURITY: All queries are validated and executed in read-only transactions
        unless skip_validation=True (only for internal health checks).

        Args:
            query: SQL SELECT statement
            params: Optional query parameters (for parameterized queries)
            fetch_all: If True, fetch all rows; if False, fetch one row
            skip_validation: If True, skip SQL validation (use only for trusted queries)

        Returns:
            List of dictionaries representing rows

        Raises:
            SQLValidationError: If query validation fails
            asyncpg.PostgresError: On database errors
            RuntimeError: If connection pool not initialized
        """
        if self.pool is None:
            raise RuntimeError(
                "PostgreSQL connection pool not initialized. "
                "Call connect() first."
            )

        # SECURITY: Validate query before execution (unless explicitly skipped)
        if not skip_validation:
            try:
                validate_query(query, allow_multiple_statements=False)
            except SQLValidationError as e:
                logger.error(f"SQL validation failed: {e}\nQuery: {query[:200]}")
                raise

        start_time = time.time()

        try:
            async with self.pool.acquire() as conn:
                # SECURITY: Execute in read-only transaction
                # This provides defense-in-depth at the database level
                async with conn.transaction(readonly=True):
                    if fetch_all:
                        rows = await conn.fetch(query, *(params or []))
                    else:
                        row = await conn.fetchrow(query, *(params or []))
                        rows = [row] if row else []

                # Convert asyncpg.Record to dict (with JSON-serializable values)
                result = [_convert_record_to_dict(row) for row in rows]

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

        except SQLValidationError:
            # Re-raise validation errors without modification
            raise
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
        queries: List[str],
        skip_validation: bool = False,
    ) -> List[List[Dict[str, Any]]]:
        """
        Execute multiple queries in a single read-only transaction.

        SECURITY: All queries are validated before execution unless skip_validation=True.

        Args:
            queries: List of SQL queries to execute
            skip_validation: If True, skip SQL validation (use only for trusted queries)

        Returns:
            List of results (one per query)

        Raises:
            SQLValidationError: If any query validation fails
            asyncpg.PostgresError: On database errors
        """
        if self.pool is None:
            raise RuntimeError("PostgreSQL connection pool not initialized")

        # SECURITY: Validate all queries before execution
        if not skip_validation:
            for i, query in enumerate(queries):
                try:
                    validate_query(query, allow_multiple_statements=False)
                except SQLValidationError as e:
                    logger.error(
                        f"SQL validation failed for query {i+1}/{len(queries)}: {e}"
                    )
                    raise

        results = []
        start_time = time.time()

        try:
            async with self.pool.acquire() as conn:
                # SECURITY: Execute all queries in a read-only transaction
                async with conn.transaction(readonly=True):
                    for query in queries:
                        rows = await conn.fetch(query)
                        results.append([_convert_record_to_dict(row) for row in rows])

            execution_time = time.time() - start_time
            logger.info(
                f"Batch query ({len(queries)} queries) executed in "
                f"{execution_time:.3f}s"
            )

            return results

        except SQLValidationError:
            raise
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

            # Simple query to test connection (skip validation for trusted query)
            result = await self.execute_query(
                "SELECT 1 as health_check",
                skip_validation=True
            )

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

        SECURITY: Validates schema and table names before querying.

        Args:
            schema: Schema name (e.g., 'dim', 'fact', 'agg')
            table: Table name

        Returns:
            Dictionary with table metadata

        Raises:
            SQLValidationError: If schema or table name is invalid
        """
        # SECURITY: Validate schema and table names to prevent SQL injection
        validate_schema(schema)
        validate_table_name(table)

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

        # Use parameterized query (skip validation - already validated parameters)
        columns = await self.execute_query(
            query,
            params=[schema, table],
            skip_validation=True
        )

        return {
            "schema": schema,
            "table": table,
            "columns": columns,
            "column_count": len(columns),
        }

    async def get_table_row_count(self, schema: str, table: str) -> int:
        """
        Get approximate row count for a table.

        SECURITY: Validates schema and table names to prevent SQL injection.

        Args:
            schema: Schema name
            table: Table name

        Returns:
            Approximate row count

        Raises:
            SQLValidationError: If schema or table name is invalid
        """
        # SECURITY: Validate schema and table names to prevent SQL injection
        # This is CRITICAL - the old implementation used f-string formatting!
        validate_schema(schema)
        validate_table_name(table)

        # Safe to use validated identifiers in query
        # Note: PostgreSQL doesn't support parameterized table/schema names,
        # so we must validate and use string interpolation
        query = f"SELECT COUNT(*) as count FROM {schema}.{table}"

        result = await self.execute_query(query, fetch_all=False, skip_validation=True)
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
