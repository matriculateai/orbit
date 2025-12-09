"""Tests for Genie client service."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from app.config import Settings
from app.services.genie_client import GenieClient


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
        GENIE_ENABLED=True,
    )


@pytest.fixture
def genie_client(mock_settings):
    """Create GenieClient instance with mock settings."""
    return GenieClient(mock_settings)


class TestGenieClient:
    """Test cases for GenieClient."""

    def test_init(self, genie_client, mock_settings):
        """Test client initialization."""
        assert genie_client.space_id == "test-space-id"
        assert "test-workspace" in genie_client.base_url

    def test_polling_constants(self, genie_client):
        """Test polling configuration constants."""
        assert genie_client.INITIAL_POLL_INTERVAL == 5
        assert genie_client.MAX_POLL_INTERVAL == 60
        assert genie_client.MAX_POLL_DURATION == 600

    def test_status_constants(self, genie_client):
        """Test status constants."""
        assert genie_client.STATUS_COMPLETED == "COMPLETED"
        assert genie_client.STATUS_FAILED == "FAILED"
        assert genie_client.STATUS_CANCELLED == "CANCELLED"


class TestGenieResponseFormatting:
    """Test cases for response formatting."""

    def test_format_response_with_query(self, genie_client):
        """Test formatting response with SQL query."""
        message = {
            "id": "msg-123",
            "status": "COMPLETED",
            "attachments": [
                {
                    "type": "query",
                    "query": {
                        "query": "SELECT * FROM sales",
                        "thinking_steps": ["Step 1", "Step 2"],
                    },
                },
                {
                    "type": "text",
                    "text": {"content": "Here are your results"},
                },
            ],
        }

        result = genie_client.format_response(message, "conv-123")

        assert result["conversation_id"] == "conv-123"
        assert result["message_id"] == "msg-123"
        assert result["sql_query"] == "SELECT * FROM sales"
        assert result["response"] == "Here are your results"
        assert result["thinking_steps"] == ["Step 1", "Step 2"]
        assert result["success"] is True

    def test_format_response_with_data(self, genie_client):
        """Test formatting response with query results."""
        message = {
            "id": "msg-123",
            "status": "COMPLETED",
            "attachments": [
                {
                    "type": "query_result",
                    "query_result": {
                        "columns": [{"name": "product"}, {"name": "sales"}],
                        "rows": [["Product A", 1000], ["Product B", 2000]],
                        "truncated": False,
                    },
                },
            ],
        }

        result = genie_client.format_response(message, "conv-123")

        assert result["data"] is not None
        assert len(result["data"]) == 2
        assert result["data"][0]["product"] == "Product A"
        assert result["data"][0]["sales"] == 1000
        assert result["columns"] == ["product", "sales"]
        assert result["truncated"] is False

    def test_format_response_truncated_data(self, genie_client):
        """Test formatting response with truncated data."""
        message = {
            "id": "msg-123",
            "status": "COMPLETED",
            "attachments": [
                {
                    "type": "query_result",
                    "query_result": {
                        "columns": [{"name": "col1"}],
                        "rows": [["val"]],
                        "truncated": True,
                    },
                },
            ],
        }

        result = genie_client.format_response(message, "conv-123")
        assert result["truncated"] is True

    def test_format_response_failed(self, genie_client):
        """Test formatting failed response."""
        message = {
            "id": "msg-123",
            "status": "FAILED",
            "error": {"message": "Query failed"},
            "attachments": [],
        }

        result = genie_client.format_response(message, "conv-123")

        assert result["success"] is False
        assert result["error"] == "Query failed"
        assert "couldn't process" in result["response"].lower()

    def test_format_response_no_content(self, genie_client):
        """Test formatting response with no content."""
        message = {
            "id": "msg-123",
            "status": "COMPLETED",
            "attachments": [],
        }

        result = genie_client.format_response(message, "conv-123")

        assert result["response"] == ""
        assert result["sql_query"] is None
        assert result["data"] is None


class TestGenieAPIOperations:
    """Test cases for Genie API operations."""

    @pytest.mark.asyncio
    async def test_list_spaces(self, genie_client):
        """Test listing Genie spaces."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "spaces": [{"id": "space-1", "name": "Test Space"}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            genie_client.client, "get", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await genie_client.list_spaces()

        assert len(result) == 1
        assert result[0]["id"] == "space-1"

    @pytest.mark.asyncio
    async def test_start_conversation(self, genie_client):
        """Test starting a new conversation."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "conversation_id": "conv-123",
            "message_id": "msg-456",
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            genie_client.client, "post", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await genie_client.start_conversation("What are my sales?")

        assert result["conversation_id"] == "conv-123"
        assert result["message_id"] == "msg-456"

    @pytest.mark.asyncio
    async def test_create_message(self, genie_client):
        """Test creating a follow-up message."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"message_id": "msg-789"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            genie_client.client, "post", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await genie_client.create_message("conv-123", "Follow up question")

        assert result["message_id"] == "msg-789"

    @pytest.mark.asyncio
    async def test_get_message(self, genie_client):
        """Test getting message status."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "msg-123",
            "status": "COMPLETED",
            "attachments": [],
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            genie_client.client, "get", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await genie_client.get_message("conv-123", "msg-123")

        assert result["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_delete_conversation(self, genie_client):
        """Test deleting a conversation."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            genie_client.client, "delete", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await genie_client.delete_conversation("conv-123")

        assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_success(self, genie_client):
        """Test successful connection test."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "spaces": [{"id": "test-space-id", "name": "Test"}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            genie_client.client, "get", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await genie_client.test_connection()

        assert result["available"] is True
        assert result["space_found"] is True

    @pytest.mark.asyncio
    async def test_test_connection_space_not_found(self, genie_client):
        """Test connection test when space not found."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "spaces": [{"id": "other-space", "name": "Other"}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            genie_client.client, "get", new_callable=AsyncMock, return_value=mock_response
        ):
            result = await genie_client.test_connection()

        assert result["available"] is True
        assert result["space_found"] is False


class TestGeniePolling:
    """Test cases for polling mechanism."""

    @pytest.mark.asyncio
    async def test_wait_for_completion_immediate(self, genie_client):
        """Test immediate completion."""
        completed_message = {"id": "msg-123", "status": "COMPLETED", "attachments": []}

        with patch.object(
            genie_client,
            "get_message",
            new_callable=AsyncMock,
            return_value=completed_message,
        ):
            result = await genie_client.wait_for_completion("conv-123", "msg-123")

        assert result["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_wait_for_completion_failed(self, genie_client):
        """Test handling failed status."""
        failed_message = {
            "id": "msg-123",
            "status": "FAILED",
            "error": {"message": "Error"},
        }

        with patch.object(
            genie_client,
            "get_message",
            new_callable=AsyncMock,
            return_value=failed_message,
        ):
            result = await genie_client.wait_for_completion("conv-123", "msg-123")

        assert result["status"] == "FAILED"

    @pytest.mark.asyncio
    async def test_wait_for_completion_polling(self, genie_client):
        """Test polling until completion."""
        executing_message = {"id": "msg-123", "status": "EXECUTING_QUERY"}
        completed_message = {"id": "msg-123", "status": "COMPLETED", "attachments": []}

        call_count = 0

        async def mock_get_message(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return executing_message
            return completed_message

        with patch.object(
            genie_client, "get_message", side_effect=mock_get_message
        ), patch("asyncio.sleep", new_callable=AsyncMock):
            result = await genie_client.wait_for_completion("conv-123", "msg-123")

        assert result["status"] == "COMPLETED"
        assert call_count == 3


class TestGenieQuery:
    """Test cases for high-level query method."""

    @pytest.mark.asyncio
    async def test_query_new_conversation(self, genie_client):
        """Test query starting new conversation."""
        start_response = {"conversation_id": "conv-123", "message_id": "msg-456"}
        completed_message = {
            "id": "msg-456",
            "status": "COMPLETED",
            "attachments": [
                {"type": "text", "text": {"content": "Results here"}}
            ],
        }

        with patch.object(
            genie_client,
            "start_conversation",
            new_callable=AsyncMock,
            return_value=start_response,
        ), patch.object(
            genie_client,
            "wait_for_completion",
            new_callable=AsyncMock,
            return_value=completed_message,
        ):
            result = await genie_client.query("What are my sales?")

        assert result["conversation_id"] == "conv-123"
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_query_existing_conversation(self, genie_client):
        """Test query in existing conversation."""
        create_response = {"message_id": "msg-789"}
        completed_message = {
            "id": "msg-789",
            "status": "COMPLETED",
            "attachments": [],
        }

        with patch.object(
            genie_client,
            "create_message",
            new_callable=AsyncMock,
            return_value=create_response,
        ), patch.object(
            genie_client,
            "wait_for_completion",
            new_callable=AsyncMock,
            return_value=completed_message,
        ):
            result = await genie_client.query(
                "Follow up question", conversation_id="conv-123"
            )

        assert result["conversation_id"] == "conv-123"

    @pytest.mark.asyncio
    async def test_query_error_handling(self, genie_client):
        """Test query error handling."""
        with patch.object(
            genie_client,
            "start_conversation",
            new_callable=AsyncMock,
            side_effect=Exception("API Error"),
        ):
            result = await genie_client.query("Test question")

        assert result["success"] is False
        assert "error" in result["response"].lower()
