"""Tests for Databricks service."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.config import Settings
from app.services.databricks import DatabricksService


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    return Settings(
        DATABRICKS_HOST="https://test-workspace.cloud.databricks.com",
        DATABRICKS_TOKEN="test_token",
        DATABRICKS_HTTP_PATH="/sql/1.0/warehouses/test",
        DATABRICKS_CATALOG="test_catalog",
        DATABRICKS_SCHEMA="test_schema",
        GENIE_SPACE_ID="test-space-id",
    )


@pytest.fixture
def databricks_service(mock_settings):
    """Create DatabricksService instance with mock settings."""
    return DatabricksService(mock_settings)


class TestDatabricksService:
    """Test cases for DatabricksService."""

    def test_init(self, databricks_service, mock_settings):
        """Test service initialization."""
        assert databricks_service.settings == mock_settings
        assert databricks_service._connection is None

    def test_get_date_filter_last_7_days(self, databricks_service):
        """Test date filter for last 7 days."""
        result = databricks_service.get_date_filter("last_7_days")
        assert "INTERVAL 7 DAYS" in result

    def test_get_date_filter_last_30_days(self, databricks_service):
        """Test date filter for last 30 days."""
        result = databricks_service.get_date_filter("last_30_days")
        assert "INTERVAL 30 DAYS" in result

    def test_get_date_filter_last_90_days(self, databricks_service):
        """Test date filter for last 90 days."""
        result = databricks_service.get_date_filter("last_90_days")
        assert "INTERVAL 90 DAYS" in result

    def test_get_date_filter_ytd(self, databricks_service):
        """Test date filter for year to date."""
        result = databricks_service.get_date_filter("ytd")
        assert "DATE_TRUNC" in result

    def test_get_date_filter_default(self, databricks_service):
        """Test date filter with invalid input returns default."""
        result = databricks_service.get_date_filter("invalid")
        assert "INTERVAL 30 DAYS" in result

    @pytest.mark.asyncio
    async def test_execute_query_success(self, databricks_service):
        """Test successful query execution."""
        mock_cursor = MagicMock()
        mock_cursor.description = [("col1",), ("col2",)]
        mock_cursor.fetchall.return_value = [("val1", "val2"), ("val3", "val4")]

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        with patch.object(
            databricks_service, "_get_connection", return_value=mock_connection
        ):
            result = await databricks_service.execute_query("SELECT 1")

        assert len(result) == 2
        assert result[0]["col1"] == "val1"
        assert result[0]["col2"] == "val2"

    @pytest.mark.asyncio
    async def test_test_connection_success(self, databricks_service):
        """Test successful connection test."""
        with patch.object(
            databricks_service,
            "execute_query",
            new_callable=AsyncMock,
            return_value=[{"test": 1}],
        ):
            result = await databricks_service.test_connection()

        assert result["connected"] is True
        assert "host" in result

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, databricks_service):
        """Test failed connection test."""
        with patch.object(
            databricks_service,
            "execute_query",
            new_callable=AsyncMock,
            side_effect=Exception("Connection failed"),
        ):
            result = await databricks_service.test_connection()

        assert result["connected"] is False
        assert "error" in result

    def test_close_connection(self, databricks_service):
        """Test closing connection."""
        mock_connection = MagicMock()
        databricks_service._connection = mock_connection

        databricks_service.close()

        mock_connection.close.assert_called_once()
        assert databricks_service._connection is None

    def test_close_no_connection(self, databricks_service):
        """Test closing when no connection exists."""
        databricks_service._connection = None
        databricks_service.close()  # Should not raise


class TestDatabricksQueries:
    """Test cases for specific Databricks queries."""

    @pytest.mark.asyncio
    async def test_get_executive_kpis(self, databricks_service):
        """Test executive KPIs query."""
        mock_sales = [{"total_sales": 1000000, "active_customers": 500}]
        mock_opps = [{"critical_gaps": 10, "opportunity_value": 50000}]

        with patch.object(
            databricks_service,
            "execute_query",
            new_callable=AsyncMock,
            side_effect=[mock_sales, mock_opps],
        ):
            result = await databricks_service.get_executive_kpis("last_30_days")

        assert result["total_sales"] == 1000000
        assert result["active_customers"] == 500
        assert result["critical_gaps"] == 10
        assert result["opportunity_value"] == 50000

    @pytest.mark.asyncio
    async def test_get_sales_trend(self, databricks_service):
        """Test sales trend query."""
        mock_data = [
            {"period": "2024-01-01", "total_sales": 100000, "customer_count": 50},
            {"period": "2024-01-02", "total_sales": 110000, "customer_count": 55},
        ]

        with patch.object(
            databricks_service,
            "execute_query",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await databricks_service.get_sales_trend("last_30_days", "daily")

        assert len(result) == 2
        assert result[0]["total_sales"] == 100000

    @pytest.mark.asyncio
    async def test_get_top_opportunities(self, databricks_service):
        """Test top opportunities query."""
        mock_data = [
            {
                "customer_id": "C1",
                "customer_name": "Customer 1",
                "product_id": "P1",
                "product_name": "Product 1",
                "opportunity_value": 5000,
            }
        ]

        with patch.object(
            databricks_service,
            "execute_query",
            new_callable=AsyncMock,
            return_value=mock_data,
        ):
            result = await databricks_service.get_top_opportunities(limit=10)

        assert len(result) == 1
        assert result[0]["opportunity_value"] == 5000

    @pytest.mark.asyncio
    async def test_get_top_opportunities_with_territory(self, databricks_service):
        """Test top opportunities with territory filter."""
        with patch.object(
            databricks_service,
            "execute_query",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_query:
            await databricks_service.get_top_opportunities(
                limit=10, territory="Western Cape"
            )

        # Verify territory filter was included in query
        call_args = mock_query.call_args[0][0]
        assert "Western Cape" in call_args
