"""Centralized Databricks SDK client for all Databricks API interactions.

This module provides a single source of truth for Databricks authentication
that works in both local development (PAT tokens) and Databricks Apps
(workspace authentication).

Best Practice: Use WorkspaceClient for all Databricks API calls.
The SDK automatically handles:
- Authentication (PAT, OAuth, workspace auth)
- Token refresh
- Retry logic
- Error handling
"""
import logging
from functools import lru_cache
from typing import Any, Dict, Optional

from databricks.sdk import WorkspaceClient
from databricks.sdk.core import Config

from app.config import Settings

logger = logging.getLogger(__name__)


class DatabricksSDKClient:
    """Centralized Databricks SDK client wrapper.

    This class provides a single WorkspaceClient instance that handles
    all authentication automatically. Use this for:
    - SQL Statement Execution API
    - Genie Conversation API
    - Any other Databricks REST APIs
    """

    def __init__(self, settings: Settings):
        """Initialize the SDK client.

        In Databricks Apps, the SDK auto-detects workspace credentials.
        In local development, it uses DATABRICKS_HOST and DATABRICKS_TOKEN.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self._client: Optional[WorkspaceClient] = None
        self._config: Optional[Config] = None

    @property
    def client(self) -> WorkspaceClient:
        """Get or create the WorkspaceClient instance.

        The SDK handles authentication automatically based on environment:
        - Databricks Apps: Uses workspace service principal
        - Local: Uses DATABRICKS_HOST + DATABRICKS_TOKEN from env/.env

        Returns:
            Configured WorkspaceClient
        """
        if self._client is None:
            logger.info("Initializing Databricks SDK WorkspaceClient")

            # Let the SDK auto-configure based on environment
            # It will use:
            # 1. Environment variables (DATABRICKS_HOST, DATABRICKS_TOKEN)
            # 2. Databricks CLI profiles (~/.databrickscfg)
            # 3. Azure/GCP/AWS native auth in cloud environments
            # 4. Workspace auth in Databricks Apps
            try:
                self._client = WorkspaceClient()
                self._config = self._client.config

                # Log auth mode for debugging
                auth_type = getattr(self._config, 'auth_type', 'unknown')
                host = getattr(self._config, 'host', 'unknown')
                logger.info(f"SDK initialized: host={host}, auth_type={auth_type}")

            except Exception as e:
                logger.error(f"Failed to initialize Databricks SDK: {e}")
                raise

        return self._client

    @property
    def config(self) -> Config:
        """Get the SDK configuration.

        Useful for passing auth to other libraries like databricks-sql-connector.

        Returns:
            SDK Config object
        """
        # Ensure client is initialized
        _ = self.client
        return self._config

    @property
    def host(self) -> str:
        """Get the Databricks workspace host URL.

        Returns:
            Workspace host URL (e.g., https://workspace.cloud.databricks.com)
        """
        return self.config.host or ""

    @property
    def auth_type(self) -> str:
        """Get the authentication type being used.

        Returns:
            Authentication type (e.g., 'pat', 'oauth', 'azure-cli')
        """
        return getattr(self.config, 'auth_type', 'unknown')

    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for manual HTTP requests.

        This is useful if you need to make raw HTTP requests outside the SDK.
        The SDK handles token refresh automatically.

        Returns:
            Dictionary with Authorization header
        """
        headers: Dict[str, str] = {}
        self.config.authenticate(headers)
        return headers

    async def execute_statement(
        self,
        statement: str,
        warehouse_id: Optional[str] = None,
        catalog: Optional[str] = None,
        schema: Optional[str] = None,
        wait_timeout: str = "30s",
    ) -> Dict[str, Any]:
        """Execute a SQL statement using the Statement Execution API.

        This is the recommended way to execute SQL in Databricks Apps.
        It uses async-compatible polling for results.

        Args:
            statement: SQL statement to execute
            warehouse_id: SQL Warehouse ID (uses settings if not provided)
            catalog: Catalog name (uses settings if not provided)
            schema: Schema name (uses settings if not provided)
            wait_timeout: How long to wait for results (e.g., "30s", "5m")

        Returns:
            Dictionary with columns and data
        """
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        wh_id = warehouse_id or self.settings.DATABRICKS_WAREHOUSE_ID
        if not wh_id:
            # Try to extract from HTTP path
            http_path = self.settings.DATABRICKS_HTTP_PATH or ""
            if "/warehouses/" in http_path:
                wh_id = http_path.split("/warehouses/")[-1]

        if not wh_id:
            raise ValueError("DATABRICKS_WAREHOUSE_ID is required for SQL execution")

        cat = catalog or self.settings.DATABRICKS_CATALOG
        sch = schema or self.settings.DATABRICKS_SCHEMA

        def _execute():
            """Execute in thread pool since SDK is synchronous."""
            response = self.client.statement_execution.execute_statement(
                warehouse_id=wh_id,
                statement=statement,
                catalog=cat,
                schema=sch,
                wait_timeout=wait_timeout,
            )
            return response

        # Run in thread pool for async compatibility
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            response = await loop.run_in_executor(executor, _execute)

        # Parse response
        result = {
            "statement_id": response.statement_id,
            "status": response.status.state.value if response.status else "UNKNOWN",
            "columns": [],
            "data": [],
        }

        if response.manifest and response.manifest.schema:
            result["columns"] = [
                col.name for col in response.manifest.schema.columns
            ]

        if response.result and response.result.data_array:
            columns = result["columns"]
            for row in response.result.data_array:
                row_dict = {}
                for i, val in enumerate(row):
                    col_name = columns[i] if i < len(columns) else f"col_{i}"
                    row_dict[col_name] = val
                result["data"].append(row_dict)

        return result

    def api_request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a raw API request using SDK authentication.

        Use this for APIs not directly supported by the SDK (like Genie).

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: API path (e.g., /api/2.0/genie/spaces)
            body: Request body for POST/PUT requests

        Returns:
            Response JSON as dictionary
        """
        return self.client.api_client.do(method, path, body=body)

    async def api_request_async(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make an async API request using SDK authentication.

        Wraps the synchronous SDK call in a thread pool for async compatibility.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: API path (e.g., /api/2.0/genie/spaces)
            body: Request body for POST/PUT requests

        Returns:
            Response JSON as dictionary
        """
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        def _request():
            return self.client.api_client.do(method, path, body=body)

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            return await loop.run_in_executor(executor, _request)

    def close(self) -> None:
        """Close the SDK client.

        Note: The SDK manages connections internally, so this is mostly
        for consistency with other service interfaces.
        """
        self._client = None
        self._config = None
        logger.info("Databricks SDK client closed")


@lru_cache()
def get_sdk_client(settings: Settings) -> DatabricksSDKClient:
    """Get a cached SDK client instance.

    Args:
        settings: Application settings

    Returns:
        Cached DatabricksSDKClient instance
    """
    return DatabricksSDKClient(settings)
