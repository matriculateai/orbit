"""Genie Chat API endpoints."""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import Settings, get_settings
from app.models.requests import GenieQueryRequest
from app.models.responses import ConversationHistoryResponse, GenieResponse
from app.services.genie_client import GenieClient
from app.services.persona_formatter import PersonaFormatter

router = APIRouter()
logger = logging.getLogger(__name__)


async def get_genie_client(
    settings: Settings = Depends(get_settings),
) -> GenieClient:
    """Dependency for Genie client."""
    if not settings.GENIE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Genie is not enabled in this environment",
        )
    return GenieClient(settings)


# ==================== Main Query Endpoint ====================


@router.post("/query", response_model=GenieResponse)
async def query_genie(
    request: GenieQueryRequest,
    genie: GenieClient = Depends(get_genie_client),
) -> GenieResponse:
    """Send a question to Genie and get a response.

    This endpoint:
    1. Starts a new conversation or continues existing one
    2. Polls for completion using exponential backoff
    3. Returns formatted response with SQL, data, and text

    Args:
        request: Query request with question and optional conversation_id

    Returns:
        GenieResponse with all response components
    """
    try:
        logger.info(f"Genie query: {request.question[:100]}...")

        result = await genie.query(
            question=request.question,
            conversation_id=request.conversation_id,
        )

        await genie.close()

        return GenieResponse(
            conversation_id=result["conversation_id"],
            message_id=result["message_id"],
            response=result["response"],
            sql_query=result.get("sql_query"),
            data=result.get("data"),
            columns=result.get("columns"),
            visualization=result.get("visualization"),
            thinking_steps=result.get("thinking_steps"),
            status=result["status"],
            success=result["success"],
            error=result.get("error"),
            truncated=result.get("truncated", False),
        )

    except HTTPException:
        raise
    except TimeoutError as e:
        logger.error(f"Genie query timeout: {e}")
        await genie.close()
        raise HTTPException(
            status_code=504,
            detail="Query timed out. Please try a simpler question.",
        )
    except Exception as e:
        logger.error(f"Genie query error: {e}")
        await genie.close()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process query: {str(e)}",
        )


# ==================== Conversation Management ====================


@router.get("/conversation/{conversation_id}/history")
async def get_conversation_history(
    conversation_id: str,
    genie: GenieClient = Depends(get_genie_client),
) -> ConversationHistoryResponse:
    """Get all messages in a conversation.

    Returns the full history of the conversation with formatted responses.
    """
    try:
        messages = await genie.get_conversation_history(conversation_id)
        await genie.close()

        return ConversationHistoryResponse(
            conversation_id=conversation_id,
            messages=messages,
            success=True,
        )

    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        await genie.close()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve conversation history: {str(e)}",
        )


@router.post("/conversation/{conversation_id}/regenerate/{message_id}")
async def regenerate_response(
    conversation_id: str,
    message_id: str,
    genie: GenieClient = Depends(get_genie_client),
) -> GenieResponse:
    """Regenerate a specific response in the conversation.

    Deletes the message and re-sends the question to get a new response.
    """
    try:
        # First, get the original message to extract the question
        messages = await genie.list_conversation_messages(conversation_id)

        # Find the user message before this assistant message
        user_question = None
        for i, msg in enumerate(messages):
            if msg.get("id") == message_id and i > 0:
                prev_msg = messages[i - 1]
                if prev_msg.get("role") == "USER":
                    # Get content from the message
                    content = prev_msg.get("content", "")
                    if not content:
                        attachments = prev_msg.get("attachments", [])
                        for att in attachments:
                            if att.get("type") == "text":
                                content = att.get("text", {}).get("content", "")
                                break
                    user_question = content
                break

        if not user_question:
            await genie.close()
            raise HTTPException(
                status_code=400,
                detail="Could not find the original question to regenerate",
            )

        # Delete the message
        await genie.delete_message(conversation_id, message_id)

        # Re-send the question
        result = await genie.query(
            question=user_question,
            conversation_id=conversation_id,
        )

        await genie.close()

        return GenieResponse(
            conversation_id=result["conversation_id"],
            message_id=result["message_id"],
            response=result["response"],
            sql_query=result.get("sql_query"),
            data=result.get("data"),
            columns=result.get("columns"),
            visualization=result.get("visualization"),
            thinking_steps=result.get("thinking_steps"),
            status=result["status"],
            success=result["success"],
            error=result.get("error"),
            truncated=result.get("truncated", False),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating response: {e}")
        await genie.close()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to regenerate response: {str(e)}",
        )


@router.delete("/conversation/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    genie: GenieClient = Depends(get_genie_client),
) -> Dict[str, Any]:
    """Delete a conversation and all its messages."""
    try:
        success = await genie.delete_conversation(conversation_id)
        await genie.close()

        if success:
            return {"success": True, "message": "Conversation deleted"}
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete conversation",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        await genie.close()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete conversation: {str(e)}",
        )


# ==================== Space & Configuration ====================


@router.get("/spaces")
async def list_spaces(
    genie: GenieClient = Depends(get_genie_client),
) -> Dict[str, Any]:
    """List all available Genie spaces."""
    try:
        spaces = await genie.list_spaces()
        await genie.close()
        return {"success": True, "spaces": spaces}
    except Exception as e:
        logger.error(f"Error listing spaces: {e}")
        await genie.close()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list spaces: {str(e)}",
        )


@router.get("/conversations")
async def list_conversations(
    genie: GenieClient = Depends(get_genie_client),
) -> Dict[str, Any]:
    """List all conversations in the configured space."""
    try:
        conversations = await genie.list_conversations()
        await genie.close()
        return {"success": True, "conversations": conversations}
    except Exception as e:
        logger.error(f"Error listing conversations: {e}")
        await genie.close()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list conversations: {str(e)}",
        )


# ==================== Suggestions ====================


@router.get("/suggestions")
async def get_suggestions(
    persona: str = Query(
        default="executive",
        description="User persona for contextual suggestions",
        regex="^(executive|manager|rep)$",
    ),
) -> Dict[str, Any]:
    """Get suggested questions based on user persona.

    Returns persona-appropriate questions to help users get started.
    """
    formatter = PersonaFormatter(persona)
    suggestions = formatter.get_suggested_questions(persona)

    return {
        "success": True,
        "persona": persona,
        "suggestions": suggestions,
    }


# ==================== Message Status ====================


@router.get("/conversation/{conversation_id}/message/{message_id}/status")
async def get_message_status(
    conversation_id: str,
    message_id: str,
    genie: GenieClient = Depends(get_genie_client),
) -> Dict[str, Any]:
    """Get the current status of a message.

    Useful for polling from the frontend if not using the main query endpoint.
    """
    try:
        message = await genie.get_message(conversation_id, message_id)
        await genie.close()

        return {
            "success": True,
            "message_id": message_id,
            "status": message.get("status", "UNKNOWN"),
            "completed": message.get("status") in ["COMPLETED", "FAILED", "CANCELLED"],
        }

    except Exception as e:
        logger.error(f"Error getting message status: {e}")
        await genie.close()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get message status: {str(e)}",
        )
