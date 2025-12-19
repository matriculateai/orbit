"""Qdrant vector search service for query history (RAG)."""
import logging
import time
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from sentence_transformers import SentenceTransformer

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class QdrantService:
    """
    Qdrant vector search service for query history (RAG).

    Provides:
    - Store successful queries with embeddings
    - Search for similar past queries
    - Collection initialization and management
    - Embedding generation using sentence-transformers
    """

    def __init__(self):
        """Initialize Qdrant client and embedding model."""
        self.client: Optional[QdrantClient] = None
        self.collection_name = settings.QDRANT_COLLECTION
        self.vector_size = settings.QDRANT_VECTOR_SIZE

        # Initialize sentence-transformers model for embeddings
        # Using 'all-MiniLM-L6-v2' (384 dimensions, fast and lightweight)
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("Loaded embedding model: all-MiniLM-L6-v2 (384 dimensions)")

    async def connect(self):
        """Initialize Qdrant client."""
        if self.client is not None:
            logger.warning("Qdrant client already initialized")
            return

        try:
            # Initialize client
            if settings.QDRANT_API_KEY:
                self.client = QdrantClient(
                    host=settings.QDRANT_HOST,
                    port=settings.QDRANT_PORT,
                    api_key=settings.QDRANT_API_KEY,
                    timeout=10,
                )
            else:
                self.client = QdrantClient(
                    host=settings.QDRANT_HOST,
                    port=settings.QDRANT_PORT,
                    timeout=10,
                )

            logger.info(
                f"Qdrant client initialized "
                f"(host={settings.QDRANT_HOST}:{settings.QDRANT_PORT})"
            )

        except Exception as e:
            logger.error(f"Failed to initialize Qdrant client: {e}")
            raise

    async def initialize_collection(self):
        """
        Create Qdrant collection if it doesn't exist.

        Collection schema:
        - Vectors: 384 dimensions (for all-MiniLM-L6-v2)
        - Distance: Cosine similarity
        - Payload: question, sql, result_sample, execution_time, created_at
        """
        if self.client is None:
            logger.warning("Qdrant client not initialized, connecting first")
            await self.connect()

        try:
            # Check if collection exists
            collections = self.client.get_collections()
            collection_names = [c.name for c in collections.collections]

            if self.collection_name in collection_names:
                logger.info(f"Collection '{self.collection_name}' already exists")
                return

            # Create collection
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,  # Cosine similarity
                ),
            )

            logger.info(
                f"Created Qdrant collection: '{self.collection_name}' "
                f"(vectors={self.vector_size}, distance=cosine)"
            )

        except Exception as e:
            logger.error(f"Error initializing Qdrant collection: {e}")
            raise

    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding vector for text.

        Args:
            text: Input text (question or query)

        Returns:
            Embedding vector (384 dimensions for all-MiniLM-L6-v2)
        """
        try:
            # Generate embedding
            embedding = self.embedding_model.encode(text)

            # Convert numpy array to list
            return embedding.tolist()

        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    async def store_query(
        self,
        question: str,
        sql: str,
        result_sample: Optional[Dict[str, Any]] = None,
        execution_time: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Store successful query in vector database.

        Args:
            question: Natural language question
            sql: Generated SQL query
            result_sample: Sample of query results (e.g., first row)
            execution_time: Query execution time in seconds
            metadata: Additional metadata (e.g., user_id, persona)
        """
        if self.client is None:
            logger.warning("Qdrant client not initialized, skipping query storage")
            return

        try:
            # Generate embedding for question
            embedding = self.embed_text(question)

            # Generate unique ID (timestamp-based)
            point_id = int(time.time() * 1000000)  # Microseconds since epoch

            # Build payload
            payload = {
                "question": question,
                "sql": sql,
                "execution_time": execution_time,
                "created_at": time.time(),
            }

            if result_sample:
                payload["result_sample"] = result_sample

            if metadata:
                payload["metadata"] = metadata

            # Store point
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload=payload,
                    )
                ],
            )

            logger.info(
                f"Stored query in Qdrant (id={point_id}, "
                f"exec_time={execution_time:.3f}s)"
            )

        except Exception as e:
            logger.error(f"Error storing query in Qdrant: {e}")
            # Don't raise - storage failure shouldn't break the request

    async def search_similar_queries(
        self,
        question: str,
        top_k: int = 3,
        score_threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar past queries.

        Args:
            question: Natural language question
            top_k: Number of similar queries to retrieve
            score_threshold: Minimum similarity score (0-1)

        Returns:
            List of similar queries with metadata
        """
        if self.client is None:
            logger.warning("Qdrant client not initialized, skipping search")
            return []

        try:
            # Generate embedding for question
            embedding = self.embed_text(question)

            # Search for similar vectors
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=embedding,
                limit=top_k,
                score_threshold=score_threshold,
            )

            # Format results
            similar_queries = []
            for result in search_results:
                similar_queries.append({
                    "question": result.payload.get("question"),
                    "sql": result.payload.get("sql"),
                    "result_sample": result.payload.get("result_sample"),
                    "execution_time": result.payload.get("execution_time"),
                    "similarity_score": result.score,
                    "created_at": result.payload.get("created_at"),
                })

            logger.info(
                f"Found {len(similar_queries)} similar queries "
                f"(threshold={score_threshold})"
            )

            return similar_queries

        except Exception as e:
            logger.error(f"Error searching Qdrant: {e}")
            return []

    async def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get collection statistics.

        Returns:
            Dictionary with collection stats
        """
        if self.client is None:
            return {"status": "not_initialized"}

        try:
            # Get collection info
            collection_info = self.client.get_collection(
                collection_name=self.collection_name
            )

            return {
                "status": "active",
                "collection_name": self.collection_name,
                "points_count": collection_info.points_count,
                "vectors_count": collection_info.vectors_count,
                "indexed_vectors_count": collection_info.indexed_vectors_count,
                "vector_size": self.vector_size,
            }

        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {"status": "error", "error": str(e)}

    async def delete_query(self, point_id: int):
        """
        Delete a specific query from the collection.

        Args:
            point_id: Point ID to delete
        """
        if self.client is None:
            logger.warning("Qdrant client not initialized")
            return

        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=[point_id],
            )

            logger.info(f"Deleted query {point_id} from Qdrant")

        except Exception as e:
            logger.error(f"Error deleting query: {e}")

    async def clear_collection(self):
        """
        Clear all queries from the collection (use with caution!).
        """
        if self.client is None:
            logger.warning("Qdrant client not initialized")
            return

        try:
            # Delete and recreate collection
            self.client.delete_collection(collection_name=self.collection_name)
            await self.initialize_collection()

            logger.warning(f"Cleared all queries from collection '{self.collection_name}'")

        except Exception as e:
            logger.error(f"Error clearing collection: {e}")

    async def health_check(self) -> bool:
        """
        Check Qdrant connection health.

        Returns:
            True if healthy, False otherwise
        """
        if self.client is None:
            logger.error("Health check failed: Qdrant client not initialized")
            return False

        try:
            # Try to get collection info
            collections = self.client.get_collections()

            if collections:
                logger.debug("Qdrant health check passed")
                return True
            else:
                logger.error("Qdrant health check failed: no collections found")
                return False

        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            return False

    async def get_recent_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get most recent queries stored in the collection.

        Args:
            limit: Number of queries to retrieve

        Returns:
            List of recent queries
        """
        if self.client is None:
            logger.warning("Qdrant client not initialized")
            return []

        try:
            # Scroll through collection to get recent points
            # Note: Qdrant doesn't natively support sorting by payload fields,
            # so we retrieve points and sort in Python
            scroll_result = self.client.scroll(
                collection_name=self.collection_name,
                limit=limit * 2,  # Get more to ensure we have enough after sorting
                with_payload=True,
                with_vectors=False,
            )

            points = scroll_result[0]

            # Sort by created_at timestamp
            sorted_points = sorted(
                points,
                key=lambda p: p.payload.get("created_at", 0),
                reverse=True,
            )[:limit]

            # Format results
            recent_queries = []
            for point in sorted_points:
                recent_queries.append({
                    "id": point.id,
                    "question": point.payload.get("question"),
                    "sql": point.payload.get("sql"),
                    "execution_time": point.payload.get("execution_time"),
                    "created_at": point.payload.get("created_at"),
                })

            logger.info(f"Retrieved {len(recent_queries)} recent queries")
            return recent_queries

        except Exception as e:
            logger.error(f"Error getting recent queries: {e}")
            return []
