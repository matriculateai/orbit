"""Databricks Genie Conversation API client (Dec 2025 Public Preview).

This client implements the latest Databricks Genie Conversation API with:
- Stateful conversations
- Exponential backoff polling
- Proper message status handling
- Response parsing for SQL, data, and text
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class GenieClient:
    """Async client for Databricks Genie Conversation API.

    Implements the Dec 2025 Public Preview API with:
    - Start conversation with initial message
    - Send follow-up messages
    - Poll for completion with exponential backoff
    - Parse attachments (SQL, data, text, visualizations)
    """

    # API endpoints
    BASE_PATH = "/api/2.0/genie"

    # Polling configuration
    INITIAL_POLL_INTERVAL = 1  # seconds
    MAX_POLL_INTERVAL = 8  # seconds (keep polling fast)
    MAX_POLL_DURATION = 90  # 90 seconds max per query

    # Status values
    STATUS_COMPLETED = "COMPLETED"
    STATUS_FAILED = "FAILED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_EXECUTING = "EXECUTING_QUERY"

    def __init__(self, settings: Settings):
        """Initialize the Genie client.

        Args:
            settings: Application settings with Databricks credentials
        """
        self.settings = settings
        self.space_id = settings.GENIE_SPACE_ID
        self.base_url = settings.DATABRICKS_HOST.rstrip("/")

        # HTTP client with auth - increased limits for parallel queries
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {settings.DATABRICKS_TOKEN}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    # ==================== Space Operations ====================

    async def list_spaces(self) -> List[Dict[str, Any]]:
        """List all available Genie spaces.

        Returns:
            List of space configurations
        """
        try:
            response = await self.client.get(f"{self.BASE_PATH}/spaces")
            response.raise_for_status()
            data = response.json()
            return data.get("spaces", [])
        except httpx.HTTPError as e:
            logger.error(f"Error listing Genie spaces: {e}")
            raise

    async def get_space(self, space_id: Optional[str] = None) -> Dict[str, Any]:
        """Get details for a specific Genie space.

        Args:
            space_id: Space ID (defaults to configured space)

        Returns:
            Space configuration details
        """
        space_id = space_id or self.space_id
        try:
            response = await self.client.get(f"{self.BASE_PATH}/spaces/{space_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error getting Genie space {space_id}: {e}")
            raise

    # ==================== Conversation Operations ====================

    async def start_conversation(
        self,
        content: str,
        space_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Start a new conversation with an initial question.

        Args:
            content: The initial question to ask Genie
            space_id: Optional space ID (defaults to configured space)

        Returns:
            Response containing conversation_id and message_id
        """
        space_id = space_id or self.space_id

        try:
            response = await self.client.post(
                f"{self.BASE_PATH}/spaces/{space_id}/start-conversation",
                json={"content": content},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error starting Genie conversation: {e}")
            raise

    async def create_message(
        self,
        conversation_id: str,
        content: str,
        space_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a follow-up message in an existing conversation.

        Args:
            conversation_id: The conversation ID
            content: The follow-up question
            space_id: Optional space ID

        Returns:
            Response containing message_id and initial status
        """
        space_id = space_id or self.space_id

        try:
            response = await self.client.post(
                f"{self.BASE_PATH}/spaces/{space_id}/conversations/{conversation_id}/messages",
                json={"content": content},
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error creating Genie message: {e}")
            raise

    async def get_message(
        self,
        conversation_id: str,
        message_id: str,
        space_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get the status and content of a specific message.

        Args:
            conversation_id: The conversation ID
            message_id: The message ID
            space_id: Optional space ID

        Returns:
            Message details including status and attachments
        """
        space_id = space_id or self.space_id

        try:
            response = await self.client.get(
                f"{self.BASE_PATH}/spaces/{space_id}/conversations/{conversation_id}/messages/{message_id}"
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error getting Genie message: {e}")
            raise

    async def list_conversation_messages(
        self,
        conversation_id: str,
        space_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List all messages in a conversation.

        Args:
            conversation_id: The conversation ID
            space_id: Optional space ID

        Returns:
            List of messages in the conversation
        """
        space_id = space_id or self.space_id

        try:
            response = await self.client.get(
                f"{self.BASE_PATH}/spaces/{space_id}/conversations/{conversation_id}/messages"
            )
            response.raise_for_status()
            data = response.json()
            return data.get("messages", [])
        except httpx.HTTPError as e:
            logger.error(f"Error listing conversation messages: {e}")
            raise

    async def list_conversations(
        self,
        space_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List all conversations in a space.

        Args:
            space_id: Optional space ID

        Returns:
            List of conversations
        """
        space_id = space_id or self.space_id

        try:
            response = await self.client.get(
                f"{self.BASE_PATH}/spaces/{space_id}/conversations"
            )
            response.raise_for_status()
            data = response.json()
            return data.get("conversations", [])
        except httpx.HTTPError as e:
            logger.error(f"Error listing conversations: {e}")
            raise

    async def delete_conversation(
        self,
        conversation_id: str,
        space_id: Optional[str] = None,
    ) -> bool:
        """Delete a conversation.

        Args:
            conversation_id: The conversation ID to delete
            space_id: Optional space ID

        Returns:
            True if deleted successfully
        """
        space_id = space_id or self.space_id

        try:
            response = await self.client.delete(
                f"{self.BASE_PATH}/spaces/{space_id}/conversations/{conversation_id}"
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError as e:
            logger.error(f"Error deleting conversation: {e}")
            return False

    async def delete_message(
        self,
        conversation_id: str,
        message_id: str,
        space_id: Optional[str] = None,
    ) -> bool:
        """Delete a specific message from a conversation.

        Args:
            conversation_id: The conversation ID
            message_id: The message ID to delete
            space_id: Optional space ID

        Returns:
            True if deleted successfully
        """
        space_id = space_id or self.space_id

        try:
            response = await self.client.delete(
                f"{self.BASE_PATH}/spaces/{space_id}/conversations/{conversation_id}/messages/{message_id}"
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError as e:
            logger.error(f"Error deleting message: {e}")
            return False

    # ==================== Query Results ====================

    async def get_query_result(
        self,
        conversation_id: str,
        message_id: str,
        attachment_id: str,
        space_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get query results for a specific attachment.

        According to API docs, query results must be fetched separately using
        the attachment_id from the query attachment.

        Endpoint: GET /api/2.0/genie/spaces/{space_id}/conversations/{conversation_id}/messages/{message_id}/attachments/{attachment_id}/query-result

        Args:
            conversation_id: The conversation ID
            message_id: The message ID
            attachment_id: The attachment ID from the query attachment
            space_id: Optional space ID

        Returns:
            Query result data with columns and rows
        """
        space_id = space_id or self.space_id

        try:
            url = (
                f"{self.BASE_PATH}/spaces/{space_id}/conversations/{conversation_id}"
                f"/messages/{message_id}/attachments/{attachment_id}/query-result"
            )
            logger.info(f"Fetching query results from: {url}")
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error getting query result: {e}")
            # Return empty result instead of raising
            return {"columns": [], "rows": [], "truncated": False}

    # ==================== Polling & Completion ====================

    async def wait_for_completion(
        self,
        conversation_id: str,
        message_id: str,
        space_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Poll for message completion with exponential backoff.

        Implements the recommended polling strategy from Dec 2025 docs:
        - Start with 5 second intervals
        - Double interval each time (max 60 seconds)
        - Timeout after 10 minutes

        Args:
            conversation_id: The conversation ID
            message_id: The message ID
            space_id: Optional space ID

        Returns:
            Completed message with all attachments
        """
        space_id = space_id or self.space_id
        poll_interval = self.INITIAL_POLL_INTERVAL
        elapsed = 0

        terminal_statuses = {
            self.STATUS_COMPLETED,
            self.STATUS_FAILED,
            self.STATUS_CANCELLED,
        }

        while elapsed < self.MAX_POLL_DURATION:
            message = await self.get_message(conversation_id, message_id, space_id)
            status = message.get("status", "UNKNOWN")

            logger.debug(f"Message {message_id} status: {status}")

            if status in terminal_statuses:
                return message

            # Wait with exponential backoff
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            # Double interval, max 60 seconds
            poll_interval = min(poll_interval * 2, self.MAX_POLL_INTERVAL)

        # Timeout reached
        raise TimeoutError(
            f"Message {message_id} did not complete within {self.MAX_POLL_DURATION} seconds"
        )

    # ==================== High-Level Query Method ====================

    async def query(
        self,
        question: str,
        conversation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send a question to Genie and wait for the response.

        This is the main method for interacting with Genie. It:
        1. Starts a new conversation or continues existing one
        2. Polls for completion
        3. Fetches query results from attachments
        4. Formats the response

        Args:
            question: The question to ask Genie
            conversation_id: Optional existing conversation ID

        Returns:
            Formatted response with SQL, data, and text
        """
        try:
            # Start new conversation or add to existing
            if conversation_id:
                response = await self.create_message(conversation_id, question)
                conv_id = conversation_id
                message_id = response.get("message_id")
            else:
                response = await self.start_conversation(question)
                # Response structure: { "conversation": {...}, "message": {...} }
                conv_data = response.get("conversation", {})
                msg_data = response.get("message", {})
                conv_id = conv_data.get("id") or response.get("conversation_id")
                message_id = msg_data.get("id") or response.get("message_id")

            if not conv_id or not message_id:
                logger.error(f"Response missing IDs: {response}")
                raise ValueError("Missing conversation_id or message_id in response")

            logger.info(f"Started conversation {conv_id}, message {message_id}")

            # Wait for completion
            completed_message = await self.wait_for_completion(conv_id, message_id)

            # Format and return response (this will also fetch query results)
            return await self.format_response(completed_message, conv_id, message_id)

        except Exception as e:
            logger.error(f"Error querying Genie: {e}", exc_info=True)
            return {
                "conversation_id": conversation_id or "",
                "message_id": "",
                "response": f"I encountered an error: {str(e)}",
                "sql_query": None,
                "data": None,
                "columns": None,
                "visualization": None,
                "thinking_steps": None,
                "status": self.STATUS_FAILED,
                "success": False,
                "error": str(e),
                "truncated": False,
            }

    # ==================== Response Formatting ====================

    async def format_response(
        self,
        message: Dict[str, Any],
        conversation_id: str,
        message_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Parse and format a Genie message response.

        Extracts:
        - SQL queries from query attachments
        - Data by fetching from query-result endpoint using attachment_id
        - Text from text attachments
        - Thinking steps for transparency

        Args:
            message: Raw message response from API
            conversation_id: The conversation ID
            message_id: The message ID (for fetching query results)

        Returns:
            Formatted response dictionary
        """
        logger.info(f"Formatting message response. Keys: {list(message.keys())}")

        msg_id = message_id or message.get("id", "")
        status = message.get("status", "UNKNOWN")
        success = status == self.STATUS_COMPLETED

        # Initialize response components
        sql_query = None
        data = None
        columns = None
        text_content = ""
        visualization = None
        thinking_steps = []
        truncated = False
        query_attachment_id = None

        # Parse attachments
        attachments = message.get("attachments") or []
        logger.info(f"Found {len(attachments)} attachments")

        for attachment in attachments:
            attach_type = attachment.get("type", "")
            attach_keys = list(attachment.keys())
            logger.info(f"Processing attachment: type={attach_type}, keys={attach_keys}")

            # Handle query attachment - check both type field AND presence of 'query' key
            # (API sometimes has empty type but has 'query' key directly)
            if attach_type == "query" or "query" in attachment:
                query_data = attachment.get("query", {})
                logger.info(f"Query data structure: {query_data}")

                # Try multiple possible locations for SQL
                sql_query = query_data.get("query")
                if not sql_query:
                    sql_query = query_data.get("sql")
                if not sql_query:
                    sql_query = query_data.get("statement")
                if not sql_query:
                    # Check if query_data itself is the SQL string
                    if isinstance(query_data, str):
                        sql_query = query_data

                # Get attachment_id for fetching results
                query_attachment_id = attachment.get("attachment_id")
                logger.info(f"Found query: sql={sql_query[:100] if sql_query else None}..., attachment_id={query_attachment_id}")

                # Extract thinking steps
                thinking = query_data.get("thinking_steps", [])
                if thinking:
                    thinking_steps.extend(thinking)
                description = query_data.get("description")
                if description and description not in thinking_steps:
                    thinking_steps.append(description)

            # Handle text attachment - check both type field AND presence of 'text' key
            # Skip if this attachment also has 'query' (already processed above)
            if (attach_type == "text" or "text" in attachment) and "query" not in attachment:
                text_data = attachment.get("text", {})
                logger.info(f"Text data structure: {text_data}")

                if isinstance(text_data, str):
                    text_content = text_data
                else:
                    text_content = (
                        text_data.get("content", "") or
                        text_data.get("value", "") or
                        text_data.get("text", "") or
                        text_data.get("body", "")
                    )
                logger.info(f"Extracted text: {text_content[:200] if text_content else 'empty'}...")

            # Handle visualization attachment
            if (attach_type == "visualization" or "visualization" in attachment) and "query" not in attachment and "text" not in attachment:
                visualization = attachment.get("visualization", {})

        # Fetch query results if we have an attachment_id
        if query_attachment_id and msg_id:
            logger.info(f"Fetching query results for attachment {query_attachment_id}")
            try:
                result = await self.get_query_result(
                    conversation_id, msg_id, query_attachment_id
                )
                logger.info(f"Query result keys: {list(result.keys())}")

                # Handle statement_response wrapper (Databricks SQL execution format)
                if "statement_response" in result:
                    stmt_response = result["statement_response"]
                    logger.info(f"statement_response keys: {list(stmt_response.keys())}")

                    # Get columns from manifest.schema.columns
                    manifest = stmt_response.get("manifest", {})
                    schema = manifest.get("schema", {})
                    raw_columns = schema.get("columns", [])
                    logger.info(f"Found {len(raw_columns)} columns in manifest.schema")

                    columns = []
                    for i, col in enumerate(raw_columns):
                        if isinstance(col, dict):
                            col_name = col.get("name", f"col_{i}")
                            columns.append(col_name)
                        else:
                            columns.append(str(col))

                    # Get rows from result.data_array
                    result_data = stmt_response.get("result", {})
                    rows = result_data.get("data_array", [])
                    logger.info(f"Found {len(rows)} rows in result.data_array")

                    # Check truncation status
                    truncated = stmt_response.get("truncated", False)

                    if columns and rows:
                        data = []
                        for row in rows:
                            if isinstance(row, dict):
                                data.append(row)
                            elif isinstance(row, (list, tuple)):
                                row_dict = {}
                                for i, col_name in enumerate(columns):
                                    row_dict[col_name] = row[i] if i < len(row) else None
                                data.append(row_dict)
                        logger.info(f"Parsed {len(data)} data rows with columns: {columns}")
                else:
                    # Fallback: try direct columns/rows structure
                    raw_columns = result.get("columns", [])
                    columns = []
                    for i, col in enumerate(raw_columns):
                        if isinstance(col, dict):
                            columns.append(col.get("name", f"col_{i}"))
                        else:
                            columns.append(str(col))

                    # Parse rows
                    rows = result.get("rows", []) or result.get("data", [])
                    truncated = result.get("truncated", False)

                    if columns and rows:
                        data = []
                        for row in rows:
                            if isinstance(row, dict):
                                data.append(row)
                            elif isinstance(row, (list, tuple)):
                                row_dict = {}
                                for i, col_name in enumerate(columns):
                                    row_dict[col_name] = row[i] if i < len(row) else None
                                data.append(row_dict)
                        logger.info(f"Parsed {len(data)} data rows with columns: {columns}")

            except Exception as e:
                logger.error(f"Failed to fetch query results: {e}")

        # Check for query_result directly on message (some API versions)
        if not data and message.get("query_result"):
            qr = message.get("query_result", {})
            raw_columns = qr.get("columns", [])
            columns = [
                col.get("name", f"col_{i}") if isinstance(col, dict) else str(col)
                for i, col in enumerate(raw_columns)
            ]
            rows = qr.get("rows", [])
            if columns and rows:
                data = []
                for row in rows:
                    if isinstance(row, dict):
                        data.append(row)
                    else:
                        row_dict = {columns[i]: row[i] if i < len(row) else None for i in range(len(columns))}
                        data.append(row_dict)

        # Build response text
        response_text = text_content
        if not response_text and data:
            response_text = f"Found {len(data)} results."
        if not response_text and sql_query:
            response_text = "Query executed successfully."
        if not response_text and status == self.STATUS_FAILED:
            error_info = message.get("error", {})
            if isinstance(error_info, dict):
                response_text = error_info.get("message", "I couldn't process that query. Please try rephrasing.")
            else:
                response_text = "I couldn't process that query. Please try rephrasing."
        if not response_text and status == self.STATUS_COMPLETED:
            response_text = "Query completed successfully."

        logger.info(f"Final response: text={response_text[:100] if response_text else 'empty'}..., "
                   f"sql={bool(sql_query)}, data_rows={len(data) if data else 0}")

        # Handle errors
        error = None
        if status == self.STATUS_FAILED:
            error_info = message.get("error", {})
            if isinstance(error_info, dict):
                error = error_info.get("message", "Unknown error")
            else:
                error = str(error_info) if error_info else "Unknown error"
            success = False

        return {
            "conversation_id": conversation_id,
            "message_id": msg_id,
            "response": response_text,
            "sql_query": sql_query,
            "data": data,
            "columns": columns,
            "visualization": visualization,
            "thinking_steps": thinking_steps if thinking_steps else None,
            "status": status,
            "success": success,
            "error": error,
            "truncated": truncated,
        }

    # ==================== Utility Methods ====================

    async def test_connection(self) -> Dict[str, Any]:
        """Test the Genie API connection.

        Returns:
            Dictionary with connection status
        """
        try:
            spaces = await self.list_spaces()
            space_found = any(s.get("id") == self.space_id for s in spaces)

            return {
                "available": True,
                "space_configured": bool(self.space_id),
                "space_found": space_found,
                "space_count": len(spaces),
            }
        except Exception as e:
            logger.error(f"Genie connection test failed: {e}")
            return {
                "available": False,
                "error": str(e),
            }

    async def get_conversation_history(
        self,
        conversation_id: str,
    ) -> List[Dict[str, Any]]:
        """Get formatted conversation history.

        Args:
            conversation_id: The conversation ID

        Returns:
            List of formatted messages
        """
        messages = await self.list_conversation_messages(conversation_id)

        formatted = []
        for msg in messages:
            msg_id = msg.get("id", "")
            formatted_msg = await self.format_response(msg, conversation_id, msg_id)
            formatted_msg["role"] = "user" if msg.get("role") == "USER" else "assistant"
            formatted.append(formatted_msg)

        return formatted
