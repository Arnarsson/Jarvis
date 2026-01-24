"""Search API endpoints."""
import logging
from fastapi import APIRouter, HTTPException

from ..search.schemas import SearchRequest, SearchResult, SearchResponse
from ..search.hybrid import hybrid_search

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post("/", response_model=SearchResponse)
async def search_memories(request: SearchRequest) -> SearchResponse:
    """Search captured memories using natural language.

    Performs hybrid search combining semantic understanding (dense vectors)
    with keyword matching (sparse vectors) using RRF fusion.

    Filters:
    - start_date/end_date: Time range filter
    - sources: Filter by content source (screen, chatgpt, claude, grok)
    """
    try:
        results = hybrid_search(request)
        return SearchResponse(
            query=request.query,
            total=len(results),
            results=results,
        )
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search failed")


@router.get("/health")
async def search_health() -> dict:
    """Check if search service is operational."""
    from ..vector.qdrant import get_qdrant

    try:
        qdrant = get_qdrant()
        # Check collection exists
        collections = qdrant.client.get_collections()
        has_captures = any(c.name == "captures" for c in collections.collections)
        return {
            "status": "healthy" if has_captures else "degraded",
            "collection_exists": has_captures,
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
