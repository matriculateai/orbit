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
    INITIAL_POLL_INTERVAL = 5  # seconds
    MAX_POLL_INTERVAL = 60  # seconds
    MAX_POLL_DURATION = 600  # 10 minutes

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

        # HTTP client with auth
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {settings.DATABRICKS_TOKEN}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
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
        3. Formats the response

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
            else:
                response = await self.start_conversation(question)
                conv_id = response.get("conversation_id")

            message_id = response.get("message_id")

            if not conv_id or not message_id:
                raise ValueError("Missing conversation_id or message_id in response")

            # Wait for completion
            completed_message = await self.wait_for_completion(conv_id, message_id)

            # Format and return response
            return self.format_response(completed_message, conv_id)

        except Exception as e:
            logger.error(f"Error querying Genie: {e}")
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

    def format_response(
        self,
        message: Dict[str, Any],
        conversation_id: str,
    ) -> Dict[str, Any]:
        """Parse and format a Genie message response.

        Extracts:
        - SQL queries from query attachments
        - Data from query_result attachments
        - Text from text attachments
        - Thinking steps for transparency

        Args:
            message: Raw message response from API
            conversation_id: The conversation ID

        Returns:
            Formatted response dictionary
        """
        logger.debug(f"Formatting message response: {message}")

        message_id = message.get("id", "")
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

        # Parse attachments
        attachments = message.get("attachments", [])
        logger.debug(f"Found {len(attachments)} attachments")

        for attachment in attachments:
            attach_type = attachment.get("type", "").lower()
            logger.debug(f"Processing attachment type: {attach_type}")

            if attach_type == "query":
                # SQL query attachment
                query_data = attachment.get("query", {})
                sql_query = query_data.get("query")
                # Also check for 'sql' key
                if not sql_query:
                    sql_query = query_data.get("sql")
                thinking = query_data.get("thinking_steps", [])
                if thinking:
                    thinking_steps.extend(thinking)
                # Also check for description as thinking
                description = query_data.get("description")
                if description and description not in thinking_steps:
                    thinking_steps.append(description)

            elif attach_type == "query_result":
                # Query result data
                result_data = attachment.get("query_result", {})
                columns = result_data.get("columns", [])
                rows = result_data.get("rows", [])
                truncated = result_data.get("truncated", False)

                # Also check for 'data' key
                if not rows:
                    rows = result_data.get("data", [])

                # Convert rows to list of dicts
                if columns and rows:
                    data = []
                    for row in rows:
                        row_dict = {}
                        # Handle both array and dict row formats
                        if isinstance(row, dict):
                            data.append(row)
                            continue
                        for i, col in enumerate(columns):
                            col_name = col.get("name", f"col_{i}") if isinstance(col, dict) else col
                            row_dict[col_name] = row[i] if i < len(row) else None
                        data.append(row_dict)
                    # Extract just column names
                    columns = [
                        col.get("name", f"col_{i}") if isinstance(col, dict) else col
                        for i, col in enumerate(columns)
                    ]
                    logger.debug(f"Parsed {len(data)} data rows with columns: {columns}")

            elif attach_type == "text":
                # Text response - check multiple possible locations
                text_data = attachment.get("text", {})
                if isinstance(text_data, str):
                    text_content = text_data
                else:
                    text_content = text_data.get("content", "")
                    # Also try 'value' key
                    if not text_content:
                        text_content = text_data.get("value", "")
                    # Also try 'text' key
                    if not text_content:
                        text_content = text_data.get("text", "")
                logger.debug(f"Extracted text content: {text_content[:100] if text_content else 'empty'}...")

            elif attach_type == "visualization":
                # Visualization config
                visualization = attachment.get("visualization", {})

        # Check for content directly on the message (some API versions)
        if not text_content:
            text_content = message.get("content", "")
        if not text_content:
            text_content = message.get("text", "")
        if not text_content:
            text_content = message.get("response", "")

        # Check for reply in message (some API versions)
        if not text_content:
            reply = message.get("reply", {})
            if isinstance(reply, str):
                text_content = reply
            elif isinstance(reply, dict):
                text_content = reply.get("content", "") or reply.get("text", "")

        # Build response text
        response_text = text_content
        if not response_text and data:
            response_text = f"Found {len(data)} results."
        if not response_text and sql_query:
            response_text = "Query executed successfully."
        if not response_text and status == self.STATUS_FAILED:
            response_text = "I couldn't process that query. Please try rephrasing."
        if not response_text and status == self.STATUS_COMPLETED:
            response_text = "Query completed."

        logger.info(f"Final response text: {response_text[:100] if response_text else 'empty'}...")

        # Handle errors
        error = None
        if status == self.STATUS_FAILED:
            error = message.get("error", {}).get("message", "Unknown error")
            if not error:
                error = message.get("error_message", "Unknown error")
            success = False

        return {
            "conversation_id": conversation_id,
            "message_id": message_id,
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
            formatted_msg = self.format_response(msg, conversation_id)
            formatted_msg["role"] = "user" if msg.get("role") == "USER" else "assistant"
            formatted.append(formatted_msg)

        return formatted
