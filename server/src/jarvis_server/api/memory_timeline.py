"""Memory Timeline API - query enriched conversation chunks.

Provides endpoints to search and browse deep conversation memory
with rich metadata filtering.
"""

import logging
from datetime import datetime

import anthropic
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from qdrant_client import models
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.config import get_settings
from jarvis_server.db.session import get_db
from jarvis_server.db.models import ConversationRecord
from jarvis_server.processing.embeddings import get_embedding_processor
from jarvis_server.vector.qdrant import get_qdrant

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v2/memory", tags=["memory"])

COLLECTION_NAME = "memory_chunks"


# Response Models
class TimelineItem(BaseModel):
    """Single timeline item."""
    date: str | None
    type: str  # decision, action, mention
    title: str
    snippet: str
    tags: list[str]
    source: str
    conversation_id: str
    chunk_index: int


class SearchResultItem(BaseModel):
    """Enhanced search result with tags."""
    conversation_id: str
    source: str
    title: str
    snippet: str
    chunk_index: int
    total_chunks: int
    date: str | None
    people: list[str]
    projects: list[str]
    topics: list[str]
    sentiment: str
    relevance_score: float


class MemoryStats(BaseModel):
    """Memory collection statistics."""
    total_conversations: int
    total_chunks: int
    date_range: dict[str, str | None]
    top_people: list[str]
    top_projects: list[str]
    decisions_count: int
    action_items_count: int
    sources: dict[str, int]


# Response containers
class TimelineResponse(BaseModel):
    """Timeline response."""
    items: list[TimelineItem]
    total: int


class SearchResponse(BaseModel):
    """Search response."""
    results: list[SearchResultItem]
    total: int


class SourceReference(BaseModel):
    """Source citation for AI answer."""
    title: str
    date: str | None
    conversation_id: str
    snippet: str


class AskRequest(BaseModel):
    """Ask question request."""
    question: str
    limit: int = 5


class AskResponse(BaseModel):
    """AI-generated answer with sources."""
    answer: str
    sources: list[SourceReference]


@router.get("/timeline", response_model=TimelineResponse)
async def get_memory_timeline(
    start: str | None = Query(None, description="Start date YYYY-MM-DD"),
    end: str | None = Query(None, description="End date YYYY-MM-DD"),
    filter_type: str | None = Query(None, description="Filter: decisions, people, projects, actions"),
    limit: int = Query(50, ge=1, le=200),
) -> TimelineResponse:
    """Get memory timeline with optional filters.
    
    Returns chronological timeline of conversation chunks filtered by type.
    """
    try:
        qdrant = get_qdrant()
        
        # Build filter conditions
        filter_conditions = []
        
        # Date range filter
        if start or end:
            filter_conditions.append(
                models.FieldCondition(
                    key="conversation_date",
                    range=models.DatetimeRange(
                        gte=start if start else None,
                        lte=end if end else None,
                    ),
                )
            )
        
        # Type-based filters
        if filter_type == "decisions":
            # Must have decisions
            filter_conditions.append(
                models.IsNullCondition(
                    is_null=models.PayloadField(key="decisions"),
                )
            )
        elif filter_type == "actions":
            # Must have action items
            filter_conditions.append(
                models.IsNullCondition(
                    is_null=models.PayloadField(key="action_items"),
                )
            )
        elif filter_type == "people":
            # Must have people mentioned
            filter_conditions.append(
                models.IsNullCondition(
                    is_null=models.PayloadField(key="people"),
                )
            )
        elif filter_type == "projects":
            # Must have projects mentioned
            filter_conditions.append(
                models.IsNullCondition(
                    is_null=models.PayloadField(key="projects"),
                )
            )
        
        filter_obj = models.Filter(must=filter_conditions) if filter_conditions else None
        
        # Scroll through collection to get timeline items
        # Note: Using scroll instead of search since we want chronological order
        results, _ = qdrant.client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=filter_obj,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        
        # Convert to timeline items
        items = []
        for point in results:
            payload = point.payload
            
            # Determine item type based on content
            item_type = "mention"
            tags = []
            
            if payload.get("decisions"):
                item_type = "decision"
                tags = payload["decisions"][:3]
            elif payload.get("action_items"):
                item_type = "action"
                tags = payload["action_items"][:3]
            elif payload.get("people"):
                tags = payload["people"][:3]
            
            if payload.get("topics"):
                tags.extend(payload["topics"][:3])
            
            items.append(TimelineItem(
                date=payload.get("conversation_date"),
                type=item_type,
                title=payload.get("title", "Untitled"),
                snippet=payload.get("chunk_text", "")[:200],
                tags=tags,
                source=payload.get("source", "unknown"),
                conversation_id=payload.get("conversation_id", ""),
                chunk_index=payload.get("chunk_index", 0),
            ))
        
        # Sort by date descending
        items.sort(key=lambda x: x.date or "", reverse=True)
        
        logger.info("memory_timeline_retrieved", count=len(items), filter=filter_type)
        return TimelineResponse(items=items, total=len(items))
        
    except Exception as e:
        logger.error("memory_timeline_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve timeline")


@router.get("/search", response_model=SearchResponse)
async def search_memory(
    q: str = Query(..., description="Search query"),
    tags: str | None = Query(None, description="Comma-separated tags to filter (people, projects, topics)"),
    sentiment: str | None = Query(None, description="Filter by sentiment: positive, negative, neutral"),
    source: str | None = Query(None, description="Filter by source: chatgpt, claude, grok"),
    start_date: str | None = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="End date filter (YYYY-MM-DD)"),
    limit: int = Query(20, ge=1, le=100),
) -> SearchResponse:
    """Enhanced semantic search over enriched memory chunks.
    
    Searches conversation chunks with optional tag and metadata filtering.
    """
    try:
        qdrant = get_qdrant()
        embedder = get_embedding_processor()
        
        # Generate query embedding
        embedding = embedder.embed(q)
        
        # Build filter conditions
        filter_conditions = []
        
        # Date range filter
        if start_date or end_date:
            filter_conditions.append(
                models.FieldCondition(
                    key="conversation_date",
                    range=models.DatetimeRange(
                        gte=start_date if start_date else None,
                        lte=end_date if end_date else None,
                    ),
                )
            )
        
        if sentiment:
            filter_conditions.append(
                models.FieldCondition(
                    key="sentiment",
                    match=models.MatchValue(value=sentiment),
                )
            )
        
        if source:
            filter_conditions.append(
                models.FieldCondition(
                    key="source",
                    match=models.MatchValue(value=source),
                )
            )
        
        # Tag filtering (if provided)
        if tags:
            tag_list = [t.strip() for t in tags.split(",")]
            # Match any of the provided tags in people, projects, or topics fields
            tag_conditions = []
            for tag in tag_list:
                tag_conditions.append(
                    models.FieldCondition(
                        key="people",
                        match=models.MatchAny(any=[tag]),
                    )
                )
                tag_conditions.append(
                    models.FieldCondition(
                        key="projects",
                        match=models.MatchAny(any=[tag]),
                    )
                )
                tag_conditions.append(
                    models.FieldCondition(
                        key="topics",
                        match=models.MatchAny(any=[tag]),
                    )
                )
            
            # OR the tag conditions
            filter_conditions.append(
                models.Filter(should=tag_conditions)
            )
        
        filter_obj = models.Filter(must=filter_conditions) if filter_conditions else None
        
        # Perform hybrid search
        results = qdrant.client.query_points(
            collection_name=COLLECTION_NAME,
            prefetch=[
                models.Prefetch(
                    query=embedding.dense.tolist(),
                    using="dense",
                    limit=limit * 2,
                    filter=filter_obj,
                ),
                models.Prefetch(
                    query=models.SparseVector(
                        indices=embedding.sparse_indices,
                        values=embedding.sparse_values,
                    ),
                    using="sparse",
                    limit=limit * 2,
                    filter=filter_obj,
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
            with_payload=True,
        )
        
        # Convert to search results
        search_results = []
        for point in results.points:
            payload = point.payload
            search_results.append(SearchResultItem(
                conversation_id=payload.get("conversation_id", ""),
                source=payload.get("source", "unknown"),
                title=payload.get("title", "Untitled"),
                snippet=payload.get("chunk_text", "")[:300],
                chunk_index=payload.get("chunk_index", 0),
                total_chunks=payload.get("total_chunks", 1),
                date=payload.get("conversation_date"),
                people=payload.get("people", []),
                projects=payload.get("projects", []),
                topics=payload.get("topics", []),
                sentiment=payload.get("sentiment", "neutral"),
                relevance_score=point.score,
            ))
        
        logger.info("memory_search_completed", query=q, results=len(search_results))
        return SearchResponse(results=search_results, total=len(search_results))
        
    except Exception as e:
        logger.error("memory_search_failed", query=q, error=str(e))
        raise HTTPException(status_code=500, detail="Search failed")


@router.get("/stats", response_model=MemoryStats)
async def get_memory_stats(
    db: AsyncSession = Depends(get_db),
) -> MemoryStats:
    """Get statistics about the memory collection."""
    try:
        qdrant = get_qdrant()
        
        # Get collection info
        try:
            collection_info = qdrant.client.get_collection(COLLECTION_NAME)
            total_chunks = collection_info.points_count or 0
        except:
            total_chunks = 0
        
        # Get conversation count from DB
        count_result = await db.execute(
            select(func.count()).select_from(ConversationRecord)
        )
        total_conversations = count_result.scalar() or 0
        
        # Get date range
        date_result = await db.execute(
            select(
                func.min(ConversationRecord.conversation_date),
                func.max(ConversationRecord.conversation_date)
            )
        )
        min_date, max_date = date_result.one()
        
        # Get source counts
        source_result = await db.execute(
            select(
                ConversationRecord.source,
                func.count()
            )
            .group_by(ConversationRecord.source)
        )
        sources = {row[0]: row[1] for row in source_result.all()}
        
        # For top people/projects/decisions, we'd need to scroll through Qdrant
        # For now, return placeholders (could be expensive operation)
        
        logger.info("memory_stats_retrieved", conversations=total_conversations, chunks=total_chunks)
        
        return MemoryStats(
            total_conversations=total_conversations,
            total_chunks=total_chunks,
            date_range={
                "start": min_date.isoformat() if min_date else None,
                "end": max_date.isoformat() if max_date else None,
            },
            top_people=[],  # Placeholder - would require aggregation
            top_projects=[],  # Placeholder
            decisions_count=0,  # Placeholder
            action_items_count=0,  # Placeholder
            sources=sources,
        )
        
    except Exception as e:
        logger.error("memory_stats_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve stats")


@router.post("/ask", response_model=AskResponse)
async def ask_memory(
    request: AskRequest,
) -> AskResponse:
    """Ask a question about your conversation history.
    
    Uses semantic search to find relevant chunks, then generates
    an AI answer with source citations.
    """
    try:
        qdrant = get_qdrant()
        embedder = get_embedding_processor()
        settings = get_settings()
        
        # Generate embedding for the question
        question_embedding = embedder.embed(request.question)
        
        # Search for relevant chunks using query_points with dense vector
        search_results = qdrant.client.query_points(
            collection_name=COLLECTION_NAME,
            query=question_embedding.dense.tolist(),
            using="dense",
            limit=request.limit,
            with_payload=True,
        )
        
        if not search_results.points:
            return AskResponse(
                answer="I couldn't find any relevant information in your conversation history to answer that question.",
                sources=[]
            )
        
        # Build context from search results
        context_chunks = []
        sources = []
        
        for point in search_results.points:
            payload = point.payload or {}
            chunk_text = payload.get("chunk_text", "")
            title = payload.get("title", "Untitled")
            date = payload.get("conversation_date")
            conv_id = payload.get("conversation_id", "")
            
            context_chunks.append(f"[{title}]\n{chunk_text}")
            
            sources.append(
                SourceReference(
                    title=title,
                    date=date,
                    conversation_id=conv_id,
                    snippet=chunk_text[:200] + "..." if len(chunk_text) > 200 else chunk_text
                )
            )
        
        # Build prompt for Claude
        context_doc = "\n\n---\n\n".join(context_chunks)
        
        prompt = f"""Based on the following excerpts from my conversation history, please answer this question:

Question: {request.question}

Context from my conversations:

{context_doc}

Please provide a clear, concise answer based on the context provided. If the context doesn't contain enough information to fully answer the question, say so. Cite specific conversations when relevant."""

        # Call Claude API
        if not settings.anthropic_api_key:
            logger.error("anthropic_api_key_missing")
            raise HTTPException(status_code=500, detail="AI service not configured")
        
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        
        answer = response.content[0].text
        
        logger.info("memory_ask_completed", question=request.question, sources_used=len(sources))
        
        return AskResponse(
            answer=answer,
            sources=sources
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("memory_ask_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to process question: {str(e)}")
