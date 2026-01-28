"""Context Handoff API - generate catch-up summaries when switching projects.

Provides AI-powered context handoffs that summarize:
- What happened last (recent conversations)
- What's pending/next (unfinished items, decisions needed)
"""

import anthropic
import structlog
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from qdrant_client import models

from jarvis_server.config import get_settings
from jarvis_server.vector.qdrant import get_qdrant
from jarvis_server.processing.embeddings import get_embedding_processor

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v2/context", tags=["context"])

COLLECTION_NAME = "memory_chunks"


# Response Models
class SourceReference(BaseModel):
    """Source reference for handoff."""
    title: str
    date: str | None
    conversation_id: str


class HandoffResponse(BaseModel):
    """Context handoff summary."""
    project: str
    last_touched: str | None
    summary: str
    pending: list[str]
    sources: list[SourceReference]
    generated_at: str


@router.get("/handoff", response_model=HandoffResponse)
async def context_handoff(
    project: str = Query(..., description="Project name to get context for"),
    limit: int = Query(10, ge=3, le=20, description="Number of recent conversations to analyze"),
) -> HandoffResponse:
    """Generate a catch-up summary for a project.
    
    Searches recent conversations about the project and uses AI to generate:
    - A 2-paragraph summary of what happened last
    - A list of pending items / next actions
    
    Perfect for context switching between projects.
    """
    try:
        qdrant = get_qdrant()
        embedder = get_embedding_processor()
        settings = get_settings()
        
        # Generate embedding for project name
        project_embedding = embedder.embed(f"{project} project status update")
        
        # Search for relevant chunks about this project
        # First try exact project tag match
        filter_by_project = models.Filter(
            must=[
                models.FieldCondition(
                    key="projects",
                    match=models.MatchAny(any=[project]),
                )
            ]
        )
        
        search_results = qdrant.client.query_points(
            collection_name=COLLECTION_NAME,
            query=project_embedding.dense.tolist(),
            using="dense",
            query_filter=filter_by_project,
            limit=limit,
            with_payload=True,
        )
        
        # If no results with exact match, try semantic search without filter
        if not search_results.points:
            logger.info("no_exact_project_match_trying_semantic", project=project)
            search_results = qdrant.client.query_points(
                collection_name=COLLECTION_NAME,
                query=project_embedding.dense.tolist(),
                using="dense",
                limit=limit,
                with_payload=True,
            )
        
        if not search_results.points:
            return HandoffResponse(
                project=project,
                last_touched=None,
                summary=f"No recent conversations found about {project}. This might be a new project or one you haven't discussed recently.",
                pending=[],
                sources=[],
                generated_at=datetime.now(timezone.utc).isoformat(),
            )
        
        # Extract context and metadata
        context_chunks = []
        sources = []
        dates = []
        
        for point in search_results.points:
            payload = point.payload or {}
            chunk_text = payload.get("chunk_text", "")
            title = payload.get("title", "Untitled")
            date = payload.get("conversation_date")
            conv_id = payload.get("conversation_id", "")
            
            if date:
                dates.append(date)
            
            # Format context with metadata
            context_chunks.append(f"[{title} - {date or 'Unknown date'}]\n{chunk_text}")
            
            sources.append(
                SourceReference(
                    title=title,
                    date=date,
                    conversation_id=conv_id,
                )
            )
        
        # Sort sources by date (most recent first)
        sources.sort(key=lambda x: x.date or "", reverse=True)
        
        # Determine last touched date
        last_touched = max(dates) if dates else None
        
        # Build context document
        context_doc = "\n\n---\n\n".join(context_chunks)
        
        # Generate handoff summary with Claude
        prompt = f"""Based on these conversation excerpts about the "{project}" project, generate a context handoff summary for someone returning to work on this project.

Context from recent conversations:

{context_doc}

Please provide:

1. A 2-paragraph summary following this structure:
   - Paragraph 1: What happened last - summarize the most recent 3-5 key discussions, decisions, or activities related to this project
   - Paragraph 2: What's pending/next - identify unfinished items, open questions, decisions needed, or follow-up actions

2. After the summary, list 3-5 specific pending action items in this format:
   PENDING:
   - Action item 1
   - Action item 2
   - Action item 3

Write in a direct, conversational tone as if briefing someone who's about to resume work. Use past tense for what happened, present/future tense for what's pending."""

        # Call Claude API
        if not settings.anthropic_api_key:
            logger.error("anthropic_api_key_missing")
            raise HTTPException(status_code=500, detail="AI service not configured")
        
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        
        answer = response.content[0].text
        
        # Parse out pending items if they exist
        pending_items = []
        summary_text = answer
        
        if "PENDING:" in answer:
            parts = answer.split("PENDING:", 1)
            summary_text = parts[0].strip()
            pending_section = parts[1].strip()
            
            # Extract bullet points
            for line in pending_section.split("\n"):
                line = line.strip()
                if line.startswith("- ") or line.startswith("* "):
                    pending_items.append(line[2:].strip())
                elif line and not line.startswith("PENDING"):
                    # Handle numbered lists or plain text
                    pending_items.append(line.lstrip("0123456789. ").strip())
        
        # Limit pending items to 5
        pending_items = pending_items[:5]
        
        logger.info(
            "context_handoff_generated",
            project=project,
            sources=len(sources),
            last_touched=last_touched,
            pending_items=len(pending_items),
        )
        
        return HandoffResponse(
            project=project,
            last_touched=last_touched,
            summary=summary_text,
            pending=pending_items,
            sources=sources[:5],  # Limit sources shown
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        
    except Exception as e:
        logger.error("context_handoff_failed", project=project, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate context handoff")
