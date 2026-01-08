"""Databricks SQL service for executing queries."""
import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from databricks import sql as databricks_sql
from databricks.sql.client import Connection, Cursor

from app.config import Settings

logger = logging.getLogger(__name__)

# Thread pool for running blocking database operations
_executor = ThreadPoolExecutor(max_workers=10)


class DatabricksService:
    """Service for executing SQL queries against Databricks SQL Warehouse.

    Supports both explicit credentials and workspace authentication for Databricks Apps.
    """

    def __init__(self, settings: Settings):
        """Initialize the Databricks service.

        Args:
            settings: Application settings with Databricks credentials
        """
        self.settings = settings
        self._connection: Optional[Connection] = None

    def _get_connection_params(self) -> Dict[str, Any]:
        """Get connection parameters based on authentication mode.

        Returns:
            Dictionary of connection parameters for databricks-sql-connector
        """
        params: Dict[str, Any] = {}

        if self.settings.use_workspace_auth:
            # Databricks Apps: Use workspace authentication
            # The SDK will automatically use the workspace credentials
            logger.info("Using workspace authentication for Databricks SQL")

            # Get host from environment or settings
            host = self.settings.effective_databricks_host
            if host:
                params["server_hostname"] = host.replace("https://", "").replace("http://", "")

            # HTTP path can come from warehouse ID or direct path
            if self.settings.DATABRICKS_HTTP_PATH:
                params["http_path"] = self.settings.DATABRICKS_HTTP_PATH
            elif self.settings.DATABRICKS_WAREHOUSE_ID:
                params["http_path"] = f"/sql/1.0/warehouses/{self.settings.DATABRICKS_WAREHOUSE_ID}"
            else:
                # Try to get from environment
                http_path = os.getenv("DATABRICKS_HTTP_PATH")
                warehouse_id = os.getenv("DATABRICKS_WAREHOUSE_ID")
                if http_path:
                    params["http_path"] = http_path
                elif warehouse_id:
                    params["http_path"] = f"/sql/1.0/warehouses/{warehouse_id}"

            # In Databricks Apps, auth is handled automatically
            # The connector will use the default credential provider chain
        else:
            # Local development: Use explicit credentials
            logger.info("Using explicit token authentication for Databricks SQL")

            if self.settings.DATABRICKS_HOST:
                params["server_hostname"] = self.settings.DATABRICKS_HOST.replace("https://", "").replace("http://", "")

            if self.settings.DATABRICKS_HTTP_PATH:
                params["http_path"] = self.settings.DATABRICKS_HTTP_PATH

            if self.settings.DATABRICKS_TOKEN:
                params["access_token"] = self.settings.DATABRICKS_TOKEN

        return params

    def _get_connection(self) -> Connection:
        """Get or create a Databricks SQL connection.

        Returns:
            Active database connection
        """
        if self._connection is None:
            logger.info("Creating new Databricks SQL connection")
            params = self._get_connection_params()

            if not params.get("server_hostname"):
                raise ValueError(
                    "DATABRICKS_HOST is required. Set it in environment or .env file."
                )
            if not params.get("http_path"):
                raise ValueError(
                    "DATABRICKS_HTTP_PATH or DATABRICKS_WAREHOUSE_ID is required. "
                    "Set it in environment or .env file."
                )

            self._connection = databricks_sql.connect(**params)
        return self._connection

    def close(self) -> None:
        """Close the database connection."""
        if self._connection is not None:
            try:
                self._connection.close()
            except Exception as e:
                logger.warning(f"Error closing connection: {e}")
            finally:
                self._connection = None

    def _execute_query_sync(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Synchronous query execution (runs in thread pool).

        Args:
            query: SQL query string
            parameters: Optional parameter dictionary

        Returns:
            List of dictionaries with query results
        """
        connection = self._get_connection()
        cursor: Cursor = connection.cursor()

        try:
            logger.debug(f"Executing query: {query[:200]}...")

            if parameters:
                cursor.execute(query, parameters)
            else:
                cursor.execute(query)

            # Get column names
            columns = [desc[0] for desc in cursor.description] if cursor.description else []

            # Fetch all results
            rows = cursor.fetchall()

            # Convert to list of dictionaries
            results = []
            for row in rows:
                row_dict = {}
                for i, value in enumerate(row):
                    row_dict[columns[i]] = value
                results.append(row_dict)

            logger.info(f"Query returned {len(results)} rows")
            return results

        finally:
            cursor.close()

    async def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Execute a SQL query and return results as a list of dictionaries.

        Args:
            query: SQL query string
            parameters: Optional parameter dictionary for parameterized queries

        Returns:
            List of dictionaries with query results
        """
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(
                _executor,
                self._execute_query_sync,
                query,
                parameters,
            )
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            raise

    async def get_table_metadata(
        self,
        table_name: str,
        catalog: Optional[str] = None,
        schema: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get metadata for a specific table.

        Args:
            table_name: Name of the table
            catalog: Optional catalog name (defaults to settings)
            schema: Optional schema name (defaults to settings)

        Returns:
            Dictionary with table metadata
        """
        catalog = catalog or self.settings.DATABRICKS_CATALOG
        schema = schema or self.settings.DATABRICKS_SCHEMA
        full_table_name = f"{catalog}.{schema}.{table_name}"

        query = f"DESCRIBE TABLE EXTENDED {full_table_name}"

        try:
            results = await self.execute_query(query)
            return {
                "table_name": full_table_name,
                "columns": results,
            }
        except Exception as e:
            logger.error(f"Error getting metadata for {full_table_name}: {e}")
            raise

    async def test_connection(self) -> Dict[str, Any]:
        """Test the Databricks SQL connection.

        Returns:
            Dictionary with connection status and details
        """
        host = self.settings.effective_databricks_host or self.settings.DATABRICKS_HOST
        try:
            results = await self.execute_query("SELECT 1 as test")
            return {
                "connected": True,
                "host": host,
                "catalog": self.settings.DATABRICKS_CATALOG,
                "schema": self.settings.DATABRICKS_SCHEMA,
                "auth_mode": "workspace" if self.settings.use_workspace_auth else "token",
            }
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return {
                "connected": False,
                "error": str(e),
                "host": host,
                "auth_mode": "workspace" if self.settings.use_workspace_auth else "token",
            }

    def get_date_filter(self, date_range: str) -> str:
        """Convert date range string to SQL date filter.

        Args:
            date_range: One of 'last_7_days', 'last_30_days', 'last_90_days', 'ytd'

        Returns:
            SQL date filter expression
        """
        date_filters = {
            "last_7_days": "date_key >= CURRENT_DATE - INTERVAL 7 DAYS",
            "last_30_days": "date_key >= CURRENT_DATE - INTERVAL 30 DAYS",
            "last_90_days": "date_key >= CURRENT_DATE - INTERVAL 90 DAYS",
            "ytd": "date_key >= DATE_TRUNC('year', CURRENT_DATE)",
        }
        return date_filters.get(date_range, date_filters["last_30_days"])

    # Dashboard Query Methods

    async def get_executive_kpis(self, date_range: str = "last_30_days") -> Dict[str, Any]:
        """Get KPIs for executive dashboard.

        Args:
            date_range: Time range for filtering

        Returns:
            Dictionary with KPI values
        """
        date_filter = self.get_date_filter(date_range)

        query = f"""
        SELECT
            COALESCE(SUM(secondary_value), 0) as total_sales,
            COUNT(DISTINCT customer_id) as active_customers
        FROM {self.settings.DATABRICKS_CATALOG}.{self.settings.DATABRICKS_SCHEMA}.fact_secondary_sales_daily
        WHERE {date_filter}
        """

        try:
            sales_results = await self.execute_query(query)

            # Get opportunity data from mv_kpi_dashboard
            opp_query = f"""
            SELECT
                COUNT(*) as critical_gaps,
                COALESCE(SUM(opportunity_value), 0) as opportunity_value
            FROM {self.settings.DATABRICKS_CATALOG}.{self.settings.DATABRICKS_SCHEMA}.mv_kpi_dashboard
            WHERE dsoh_days < 45 AND opportunity_value > 0
            """
            opp_results = await self.execute_query(opp_query)

            return {
                "total_sales": float(sales_results[0].get("total_sales", 0)) if sales_results else 0,
                "active_customers": int(sales_results[0].get("active_customers", 0)) if sales_results else 0,
                "opportunity_value": float(opp_results[0].get("opportunity_value", 0)) if opp_results else 0,
                "critical_gaps": int(opp_results[0].get("critical_gaps", 0)) if opp_results else 0,
                "period": date_range,
            }
        except Exception as e:
            logger.error(f"Error getting executive KPIs: {e}")
            raise

    async def get_sales_trend(
        self,
        date_range: str = "last_90_days",
        granularity: str = "daily",
    ) -> List[Dict[str, Any]]:
        """Get sales trend data for charts.

        Args:
            date_range: Time range for filtering
            granularity: 'daily', 'weekly', or 'monthly'

        Returns:
            List of dictionaries with date and sales values
        """
        date_filter = self.get_date_filter(date_range)

        if granularity == "monthly":
            date_expr = "DATE_TRUNC('month', date_key)"
        elif granularity == "weekly":
            date_expr = "DATE_TRUNC('week', date_key)"
        else:
            date_expr = "date_key"

        query = f"""
        SELECT
            {date_expr} as period,
            SUM(secondary_value) as total_sales,
            COUNT(DISTINCT customer_id) as customer_count
        FROM {self.settings.DATABRICKS_CATALOG}.{self.settings.DATABRICKS_SCHEMA}.fact_secondary_sales_daily
        WHERE {date_filter}
        GROUP BY {date_expr}
        ORDER BY {date_expr}
        """

        try:
            results = await self.execute_query(query)
            return [
                {
                    "period": str(r["period"]),
                    "total_sales": float(r.get("total_sales", 0)),
                    "customer_count": int(r.get("customer_count", 0)),
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"Error getting sales trend: {e}")
            raise

    async def get_top_opportunities(
        self,
        limit: int = 10,
        region: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get top stock opportunities from mv_kpi_dashboard.

        Args:
            limit: Maximum number of opportunities to return
            region: Optional region filter

        Returns:
            List of opportunity dictionaries
        """
        region_filter = f"AND region = '{region}'" if region else ""

        # Using actual mv_kpi_dashboard columns
        query = f"""
        SELECT
            product_code,
            product_name,
            brand,
            customer_name,
            customer_group,
            region,
            soh,
            avg_daily_units,
            dsoh_days,
            ideal_stock_45d_units,
            opportunity_units,
            opportunity_value
        FROM {self.settings.DATABRICKS_CATALOG}.{self.settings.DATABRICKS_SCHEMA}.mv_kpi_dashboard
        WHERE dsoh_days < 45
            AND opportunity_value > 0
            {region_filter}
        ORDER BY opportunity_value DESC
        LIMIT {limit}
        """

        try:
            return await self.execute_query(query)
        except Exception as e:
            logger.error(f"Error getting top opportunities: {e}")
            raise

    async def get_territory_data(
        self,
        territory_id: str,
        date_range: str = "last_30_days",
    ) -> Dict[str, Any]:
        """Get territory-specific data for manager dashboard.

        Note: territory_id corresponds to dim_rep.territory, which is used
        to filter reps. For customer/product data, we use region from dim_customer.

        Args:
            territory_id: Territory identifier (from dim_rep)
            date_range: Time range for filtering

        Returns:
            Dictionary with territory data
        """
        date_filter = self.get_date_filter(date_range)

        # Get the region for this territory from dim_rep
        region_query = f"""
        SELECT DISTINCT region
        FROM {self.settings.DATABRICKS_CATALOG}.{self.settings.DATABRICKS_SCHEMA}.dim_rep
        WHERE territory = '{territory_id}'
        LIMIT 1
        """

        try:
            region_results = await self.execute_query(region_query)
            region = region_results[0]["region"] if region_results else None

            # Product performance query - using region from dim_customer
            product_query = f"""
            SELECT
                p.product_id,
                p.product_code,
                p.product_name,
                p.brand,
                SUM(s.secondary_value) as total_sales,
                SUM(s.delivered_qty) as units_sold,
                COUNT(DISTINCT s.customer_id) as customer_count
            FROM {self.settings.DATABRICKS_CATALOG}.{self.settings.DATABRICKS_SCHEMA}.fact_secondary_sales_daily s
            JOIN {self.settings.DATABRICKS_CATALOG}.{self.settings.DATABRICKS_SCHEMA}.dim_product p
                ON s.product_id = p.product_id
            JOIN {self.settings.DATABRICKS_CATALOG}.{self.settings.DATABRICKS_SCHEMA}.dim_customer c
                ON s.customer_id = c.customer_id
            WHERE c.region = '{region}' AND {date_filter}
            GROUP BY p.product_id, p.product_code, p.product_name, p.brand
            ORDER BY total_sales DESC
            LIMIT 10
            """ if region else None

            # Rep performance query - filter by territory
            rep_query = f"""
            SELECT
                r.rep_id,
                r.rep_name,
                r.rep_code,
                a.coverage_percent,
                a.strike_rate,
                a.total_calls,
                a.productive_calls,
                r.territory,
                r.region
            FROM {self.settings.DATABRICKS_CATALOG}.{self.settings.DATABRICKS_SCHEMA}.fact_rep_activity_monthly a
            JOIN {self.settings.DATABRICKS_CATALOG}.{self.settings.DATABRICKS_SCHEMA}.dim_rep r
                ON a.rep_id = r.rep_id
            WHERE r.territory = '{territory_id}'
                AND a.yyyymm = DATE_FORMAT(CURRENT_DATE - INTERVAL 1 MONTH, 'yyyyMM')
            ORDER BY a.strike_rate DESC
            """

            products = await self.execute_query(product_query) if product_query else []
            reps = await self.execute_query(rep_query)
            opportunities = await self.get_top_opportunities(limit=20, region=region)

            return {
                "territory_id": territory_id,
                "region": region,
                "product_performance": products,
                "rep_performance": reps,
                "opportunities": opportunities,
            }
        except Exception as e:
            logger.error(f"Error getting territory data: {e}")
            raise

    async def get_rep_dashboard_data(
        self,
        rep_id: str,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Get rep-specific dashboard data.

        Args:
            rep_id: Rep identifier
            limit: Maximum opportunities to return

        Returns:
            Dictionary with rep dashboard data
        """
        # Rep performance query
        perf_query = f"""
        SELECT
            r.rep_id,
            r.rep_name,
            r.rep_code,
            a.coverage_percent,
            a.strike_rate,
            a.total_calls,
            a.productive_calls,
            a.customers_seen,
            r.territory,
            r.region
        FROM {self.settings.DATABRICKS_CATALOG}.{self.settings.DATABRICKS_SCHEMA}.fact_rep_activity_monthly a
        JOIN {self.settings.DATABRICKS_CATALOG}.{self.settings.DATABRICKS_SCHEMA}.dim_rep r
            ON a.rep_id = r.rep_id
        WHERE r.rep_id = '{rep_id}'
            AND a.yyyymm = DATE_FORMAT(CURRENT_DATE - INTERVAL 1 MONTH, 'yyyyMM')
        """

        # Get rep's region for opportunities
        region_query = f"""
        SELECT region FROM {self.settings.DATABRICKS_CATALOG}.{self.settings.DATABRICKS_SCHEMA}.dim_rep
        WHERE rep_id = '{rep_id}'
        """

        try:
            perf_results = await self.execute_query(perf_query)
            my_performance = perf_results[0] if perf_results else None

            region_results = await self.execute_query(region_query)
            region = region_results[0]["region"] if region_results else None

            opportunities = []
            if region:
                opportunities = await self.get_top_opportunities(limit=limit, region=region)

            # Priority opportunities (top 5 by value)
            priority = opportunities[:5] if opportunities else []

            return {
                "rep_id": rep_id,
                "my_performance": my_performance,
                "priority_opportunities": priority,
                "all_opportunities": opportunities,
            }
        except Exception as e:
            logger.error(f"Error getting rep dashboard data: {e}")
            raise
