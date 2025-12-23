"""
Integration tests for PostgresService security features.

Tests read-only transaction enforcement and SQL validation integration.
These tests require a PostgreSQL database connection to run.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.postgres import PostgresService
from app.security import SQLValidationError


class TestPostgresServiceValidation:
    """Test SQL validation in PostgresService."""

    @pytest.fixture
    def mock_pool(self):
        """Mock asyncpg connection pool."""
        pool = AsyncMock()
        pool.acquire = MagicMock()
        return pool

    @pytest.fixture
    def postgres_service(self, mock_pool):
        """Create PostgresService with mocked pool."""
        service = PostgresService()
        service.pool = mock_pool
        return service

    @pytest.mark.asyncio
    async def test_validates_query_by_default(self, postgres_service):
        """execute_query should validate SQL by default."""
        dangerous_query = "DROP TABLE users"

        with pytest.raises(SQLValidationError, match="Dangerous SQL keyword"):
            await postgres_service.execute_query(dangerous_query)

    @pytest.mark.asyncio
    async def test_skip_validation_for_trusted_queries(self, postgres_service, mock_pool):
        """execute_query should allow skipping validation for trusted queries."""
        # Mock the database response
        mock_conn = AsyncMock()
        mock_transaction = AsyncMock()
        mock_transaction.__aenter__ = AsyncMock(return_value=mock_transaction)
        mock_transaction.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction = MagicMock(return_value=mock_transaction)
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire = MagicMock(return_value=mock_context)

        # This is a trusted internal query
        query = "SELECT 1 as health_check"
        result = await postgres_service.execute_query(query, skip_validation=True)

        assert result == []
        mock_conn.transaction.assert_called_once_with(readonly=True)

    @pytest.mark.asyncio
    async def test_validates_all_batch_queries(self, postgres_service):
        """execute_query_batch should validate all queries."""
        queries = [
            "SELECT * FROM dim.product",
            "DROP TABLE users",  # Dangerous
            "SELECT * FROM fact.secondary_sales_daily",
        ]

        with pytest.raises(SQLValidationError, match="Dangerous SQL keyword"):
            await postgres_service.execute_query_batch(queries)

    @pytest.mark.asyncio
    async def test_enforces_readonly_transaction(self, postgres_service, mock_pool):
        """All queries should execute in read-only transactions."""
        mock_conn = AsyncMock()
        mock_transaction = AsyncMock()
        mock_transaction.__aenter__ = AsyncMock(return_value=mock_transaction)
        mock_transaction.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction = MagicMock(return_value=mock_transaction)
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        mock_pool.acquire = MagicMock(return_value=mock_context)

        query = "SELECT * FROM dim.product"
        await postgres_service.execute_query(query)

        # Verify transaction was called with readonly=True
        mock_conn.transaction.assert_called_once_with(readonly=True)


class TestIdentifierValidationIntegration:
    """Test identifier validation in PostgresService methods."""

    @pytest.fixture
    def postgres_service(self):
        """Create PostgresService instance."""
        service = PostgresService()
        service.pool = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_get_table_info_validates_schema(self, postgres_service):
        """get_table_info should validate schema name."""
        with pytest.raises(SQLValidationError, match="not allowed"):
            await postgres_service.get_table_info("evil_schema", "users")

    @pytest.mark.asyncio
    async def test_get_table_info_validates_table(self, postgres_service):
        """get_table_info should validate table name."""
        with pytest.raises(SQLValidationError, match="Invalid identifier"):
            await postgres_service.get_table_info("dim", "'; DROP TABLE users--")

    @pytest.mark.asyncio
    async def test_get_table_row_count_validates_schema(self, postgres_service):
        """get_table_row_count should validate schema name."""
        with pytest.raises(SQLValidationError, match="not allowed"):
            await postgres_service.get_table_row_count("pg_catalog", "pg_tables")

    @pytest.mark.asyncio
    async def test_get_table_row_count_validates_table(self, postgres_service):
        """get_table_row_count should validate table name."""
        with pytest.raises(SQLValidationError, match="Invalid identifier"):
            await postgres_service.get_table_row_count("dim", "users'; DELETE FROM users--")

    @pytest.mark.asyncio
    async def test_get_table_info_allows_valid_identifiers(self, postgres_service):
        """get_table_info should allow valid schema and table names."""
        mock_conn = AsyncMock()
        mock_transaction = AsyncMock()
        mock_transaction.__aenter__ = AsyncMock(return_value=mock_transaction)
        mock_transaction.__aexit__ = AsyncMock(return_value=None)
        mock_conn.transaction = MagicMock(return_value=mock_transaction)
        mock_conn.fetch = AsyncMock(return_value=[])

        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_context.__aexit__ = AsyncMock(return_value=None)
        postgres_service.pool.acquire = MagicMock(return_value=mock_context)

        # Valid schema and table
        result = await postgres_service.get_table_info("dim", "product")

        assert result["schema"] == "dim"
        assert result["table"] == "product"
        assert result["columns"] == []


class TestSecurityErrorHandling:
    """Test error handling for security violations."""

    @pytest.fixture
    def postgres_service(self):
        """Create PostgresService instance."""
        service = PostgresService()
        service.pool = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_validation_error_propagates(self, postgres_service):
        """SQLValidationError should propagate to caller."""
        dangerous_query = "DELETE FROM users"

        with pytest.raises(SQLValidationError) as exc_info:
            await postgres_service.execute_query(dangerous_query)

        assert "Dangerous SQL keyword" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validation_error_logged(self, postgres_service):
        """Validation errors should be logged."""
        dangerous_query = "UPDATE users SET admin = true"

        with patch('app.services.postgres.logger') as mock_logger:
            with pytest.raises(SQLValidationError):
                await postgres_service.execute_query(dangerous_query)

            # Verify error was logged
            mock_logger.error.assert_called()
            log_call = mock_logger.error.call_args[0][0]
            assert "SQL validation failed" in log_call


class TestReadOnlyTransactionEnforcement:
    """Test read-only transaction enforcement prevents writes."""

    @pytest.mark.asyncio
    async def test_readonly_transaction_blocks_writes(self):
        """
        Read-only transactions should block write operations.

        Note: This requires an actual database connection to test properly.
        This is a placeholder for integration testing.
        """
        # This test would require a real database connection
        # It's included here as documentation of expected behavior
        pass

    @pytest.mark.asyncio
    async def test_readonly_transaction_allows_reads(self):
        """
        Read-only transactions should allow read operations.

        Note: This requires an actual database connection to test properly.
        This is a placeholder for integration testing.
        """
        # This test would require a real database connection
        # It's included here as documentation of expected behavior
        pass


class TestSecurityConfiguration:
    """Test security configuration from settings."""

    def test_default_validation_enabled(self):
        """SQL validation should be enabled by default."""
        from app.config import get_settings
        settings = get_settings()
        assert settings.SQL_ENABLE_VALIDATION is True

    def test_default_allowed_schemas(self):
        """Default allowed schemas should be configured."""
        from app.config import get_settings
        settings = get_settings()
        assert "dim" in settings.SQL_ALLOWED_SCHEMAS
        assert "fact" in settings.SQL_ALLOWED_SCHEMAS
        assert "agg" in settings.SQL_ALLOWED_SCHEMAS

    def test_query_limits_configured(self):
        """Query and result limits should be configured."""
        from app.config import get_settings
        settings = get_settings()
        assert settings.SQL_MAX_QUERY_LENGTH > 0
        assert settings.SQL_MAX_RESULT_ROWS > 0
