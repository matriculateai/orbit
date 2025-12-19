"""AI Chat API endpoints for natural language queries."""
import logging
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.dependencies import get_postgres, get_redis, get_qdrant, get_claude
from app.services.postgres import PostgresService
from app.services.redis_service import RedisService
from app.services.qdrant_service import QdrantService
from app.services.claude_service import ClaudeService

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Request/Response Models
# ============================================================================

class ChatRequest(BaseModel):
    """Natural language query request."""
    question: str = Field(
        ...,
        description="Natural language question about the data",
        min_length=3,
        max_length=500,
    )
    persona: Optional[str] = Field(
        default="executive",
        description="User persona (executive, manager, rep)",
        pattern="^(executive|manager|rep)$",
    )
    use_rag: bool = Field(
        default=True,
        description="Use RAG (retrieve similar past queries)",
    )
    use_cache: bool = Field(
        default=True,
        description="Use cached results if available",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "question": "What are the top 5 products by sales last month?",
                "persona": "executive",
                "use_rag": True,
                "use_cache": True,
            }
        }


class ChatResponse(BaseModel):
    """Natural language query response."""
    success: bool
    question: str
    answer: str
    sql: str
    data: List[Dict[str, Any]]
    metadata: Dict[str, Any] = Field(
        description="Query metadata (execution time, model used, etc.)"
    )
    cached: bool = Field(default=False)

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "question": "What are the top 5 products by sales last month?",
                "answer": "The top 5 products by sales last month are...",
                "sql": "SELECT product_name, SUM(secondary_value) as total_sales...",
                "data": [
                    {"product_name": "Disprin 100s", "total_sales": 125000.50}
                ],
                "metadata": {
                    "execution_time": 1.23,
                    "model": "claude-haiku-4.5-20251022",
                    "complexity": "simple",
                    "row_count": 5,
                },
                "cached": False,
            }
        }


class QueryHistoryResponse(BaseModel):
    """Recent query history response."""
    success: bool
    queries: List[Dict[str, Any]]
    total_count: int


# ============================================================================
# Chat Endpoints
# ============================================================================

@router.post("/query", response_model=ChatResponse)
async def query_chat(
    request: ChatRequest,
    postgres: PostgresService = Depends(get_postgres),
    redis: RedisService = Depends(get_redis),
    qdrant: QdrantService = Depends(get_qdrant),
    claude: ClaudeService = Depends(get_claude),
) -> ChatResponse:
    """
    Process natural language query and return results.

    This endpoint:
    1. Checks cache for existing results
    2. Uses Claude AI to generate SQL from question
    3. Routes to Haiku (simple) or Sonnet (complex) based on complexity
    4. Optionally uses RAG to retrieve similar past queries
    5. Executes SQL against Supabase PostgreSQL
    6. Generates natural language answer from results
    7. Caches results and stores query in Qdrant for future RAG

    Args:
        request: Natural language query request

    Returns:
        ChatResponse with answer, SQL, data, and metadata
    """
    start_time = time.time()

    try:
        # Step 1: Check cache
        cache_key = None
        if request.use_cache and redis:
            cache_key = redis.generate_cache_key(
                f"chat:{request.question}",
                {"persona": request.persona}
            )
            cached_result = await redis.get_cached_result(cache_key)

            if cached_result:
                logger.info(f"Cache HIT for question: {request.question}")
                return ChatResponse(**cached_result, cached=True)

        # Step 2: Generate SQL using Claude
        logger.info(f"Generating SQL for question: {request.question}")

        sql_result = await claude.generate_sql(
            question=request.question,
            use_rag=request.use_rag
        )

        sql = sql_result["sql"]
        model = sql_result["model"]
        complexity = sql_result["complexity"]

        logger.info(
            f"SQL generated using {model} (complexity: {complexity})\n"
            f"SQL: {sql[:200]}..."
        )

        # Step 3: Execute SQL
        data = await postgres.execute_query(sql)

        # Step 4: Generate natural language answer
        answer = await claude.generate_answer_from_results(
            question=request.question,
            sql=sql,
            results=data
        )

        # Calculate execution time
        execution_time = time.time() - start_time

        # Build metadata
        metadata = {
            "execution_time": round(execution_time, 3),
            "model": model,
            "complexity": complexity,
            "row_count": len(data),
            "sql_length": len(sql),
            "rag_used": request.use_rag and len(sql_result.get("similar_queries", [])) > 0,
            "similar_queries_count": len(sql_result.get("similar_queries", [])),
        }

        # Build response
        response_data = {
            "success": True,
            "question": request.question,
            "answer": answer,
            "sql": sql,
            "data": data,
            "metadata": metadata,
            "cached": False,
        }

        # Step 5: Cache result
        if request.use_cache and redis and cache_key:
            await redis.cache_result(cache_key, response_data)

        # Step 6: Store query in Qdrant for future RAG
        if qdrant and data:
            await qdrant.store_query(
                question=request.question,
                sql=sql,
                result_sample=data[0] if data else None,
                execution_time=execution_time,
                metadata={"persona": request.persona}
            )

        logger.info(
            f"Query completed in {execution_time:.3f}s, "
            f"returned {len(data)} rows"
        )

        return ChatResponse(**response_data)

    except ValueError as e:
        # SQL safety validation error
        logger.error(f"SQL safety validation failed: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid SQL query: {str(e)}"
        )

    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process query: {str(e)}"
        )


@router.get("/history", response_model=QueryHistoryResponse)
async def get_query_history(
    limit: int = 10,
    qdrant: QdrantService = Depends(get_qdrant),
) -> QueryHistoryResponse:
    """
    Get recent query history.

    Args:
        limit: Number of queries to retrieve (default: 10, max: 50)

    Returns:
        Recent queries with metadata
    """
    try:
        if not qdrant:
            return QueryHistoryResponse(
                success=True,
                queries=[],
                total_count=0,
            )

        # Limit to max 50
        limit = min(limit, 50)

        # Get recent queries from Qdrant
        recent_queries = await qdrant.get_recent_queries(limit=limit)

        return QueryHistoryResponse(
            success=True,
            queries=recent_queries,
            total_count=len(recent_queries),
        )

    except Exception as e:
        logger.error(f"Error retrieving query history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve query history: {str(e)}"
        )


@router.get("/stats")
async def get_chat_stats(
    redis: RedisService = Depends(get_redis),
    qdrant: QdrantService = Depends(get_qdrant),
) -> Dict[str, Any]:
    """
    Get chat system statistics.

    Returns:
        Statistics about cache, vector DB, etc.
    """
    try:
        stats = {
            "cache": None,
            "vector_db": None,
        }

        # Get cache stats
        if redis:
            stats["cache"] = await redis.get_cache_stats()

        # Get Qdrant stats
        if qdrant:
            stats["vector_db"] = await qdrant.get_collection_stats()

        return {
            "success": True,
            "stats": stats,
        }

    except Exception as e:
        logger.error(f"Error getting chat stats: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get chat stats: {str(e)}"
        )


@router.post("/clear-cache")
async def clear_cache(
    redis: RedisService = Depends(get_redis),
) -> Dict[str, Any]:
    """
    Clear all cached query results.

    Use with caution!
    """
    try:
        if not redis:
            return {
                "success": False,
                "message": "Redis not available",
            }

        await redis.invalidate_cache("query_cache:*")

        return {
            "success": True,
            "message": "Cache cleared successfully",
        }

    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear cache: {str(e)}"
        )
