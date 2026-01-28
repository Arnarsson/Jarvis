"""Hybrid search combining dense and sparse vectors with RRF fusion."""
import logging
from datetime import datetime
from qdrant_client import models

from ..vector.qdrant import get_qdrant
from ..processing.embeddings import get_embedding_processor
from .schemas import SearchRequest, SearchResult

logger = logging.getLogger(__name__)

COLLECTION_NAME = "captures"


def hybrid_search(request: SearchRequest) -> list[SearchResult]:
    """Execute hybrid search with dense + sparse vectors and RRF fusion.

    Uses Qdrant's prefetch to get top-k from each vector type,
    then fuses results using Reciprocal Rank Fusion (RRF).
    """
    qdrant = get_qdrant()
    embedder = get_embedding_processor()

    # Generate query embeddings
    embedding = embedder.embed(request.query)

    # Build filter conditions
    filter_conditions = []

    if request.start_date or request.end_date:
        filter_conditions.append(
            models.FieldCondition(
                key="timestamp",
                range=models.DatetimeRange(
                    gte=request.start_date.isoformat() if request.start_date else None,
                    lte=request.end_date.isoformat() if request.end_date else None,
                ),
            )
        )

    if request.sources:
        filter_conditions.append(
            models.FieldCondition(
                key="source",
                match=models.MatchAny(any=request.sources),
            )
        )

    filter_condition = models.Filter(must=filter_conditions) if filter_conditions else None

    # Prefetch limits - get more candidates for better fusion
    prefetch_limit = min(request.limit * 5, 50)

    # Execute hybrid search with RRF fusion
    results = qdrant.client.query_points(
        collection_name=COLLECTION_NAME,
        prefetch=[
            models.Prefetch(
                query=embedding.dense.tolist(),
                using="dense",
                limit=prefetch_limit,
                filter=filter_condition,
            ),
            models.Prefetch(
                query=models.SparseVector(
                    indices=embedding.sparse_indices,
                    values=embedding.sparse_values,
                ),
                using="sparse",
                limit=prefetch_limit,
                filter=filter_condition,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=request.limit,
        with_payload=True,
    )

    # Convert to SearchResult objects
    search_results = []
    for point in results.points:
        payload = point.payload or {}
        timestamp_str = payload.get("timestamp")

        # Parse timestamp
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                timestamp = datetime.now()
        else:
            timestamp = datetime.now()

        search_results.append(
            SearchResult(
                id=str(point.id),
                score=point.score or 0.0,
                text_preview=payload.get("text_preview", ""),
                timestamp=timestamp,
                source=payload.get("source", "screen"),
                filepath=payload.get("filepath"),
                title=payload.get("title"),
                subject=payload.get("subject"),
                snippet=payload.get("snippet"),
                metadata={k: v for k, v in payload.items() if k not in {"text_preview", "timestamp", "filepath"}},
            )
        )

    logger.info(f"Hybrid search for '{request.query[:50]}...' returned {len(search_results)} results")
    return search_results
