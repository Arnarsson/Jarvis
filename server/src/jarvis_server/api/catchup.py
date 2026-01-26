"""Catch Me Up API - contextual summaries from all data sources."""

import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from jarvis_server.search.schemas import SearchRequest
from jarvis_server.search.hybrid import hybrid_search
from jarvis_server.catchup.summarizer import Summarizer

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/catchup", tags=["catchup"])


@dataclass
class ContextItem:
    """A piece of context from any source."""
    source: str
    timestamp: datetime
    content: str
    metadata: dict[str, Any]
    relevance: float = 1.0


@dataclass
class GatheredContext:
    """All context gathered for a topic."""
    topic: str
    timeframe_start: datetime | None
    timeframe_end: datetime | None
    items: list[ContextItem]
    total_sources: dict[str, int]


class CatchUpRequest(BaseModel):
    """Request for catch-up summary."""
    topic: str = Field(..., description="Topic to catch up on")
    days_back: int = Field(default=7, ge=1, le=90, description="Days to look back")
    style: str = Field(default="detailed", pattern="^(summary|detailed)$")


class CatchUpResponse(BaseModel):
    """Response with catch-up summary."""
    topic: str
    summary: str
    sources_searched: dict[str, int]
    timeframe_days: int
    generated_at: datetime


async def gather_context(topic: str, days_back: int = 7) -> GatheredContext:
    """Gather context from all sources using hybrid search."""
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days_back)

    # Search across all sources
    request = SearchRequest(
        query=topic,
        sources=["screen", "email", "chatgpt", "claude", "grok"],
        limit=30,
        start_date=start_date,
        end_date=end_date,
    )

    results = hybrid_search(request)

    items: list[ContextItem] = []
    totals: dict[str, int] = {}

    for result in results:
        source = result.source
        totals[source] = totals.get(source, 0) + 1

        items.append(ContextItem(
            source=source,
            timestamp=result.timestamp,
            content=result.text_preview or "",
            metadata={"id": result.id, "score": result.score},
            relevance=result.score or 0.5,
        ))

    items.sort(key=lambda x: x.timestamp)

    return GatheredContext(
        topic=topic,
        timeframe_start=start_date,
        timeframe_end=end_date,
        items=items,
        total_sources=totals,
    )


@router.post("/", response_model=CatchUpResponse)
async def catch_me_up(request: CatchUpRequest):
    """Get a contextual summary to catch up on a topic."""
    logger.info(f"Catch-up request for topic: {request.topic}")

    try:
        # Gather context
        context = await gather_context(request.topic, request.days_back)

        # Generate summary
        summarizer = Summarizer()
        summary = await summarizer.summarize(context, style=request.style)

        return CatchUpResponse(
            topic=request.topic,
            summary=summary,
            sources_searched=context.total_sources,
            timeframe_days=request.days_back,
            generated_at=datetime.utcnow(),
        )
    except Exception as e:
        logger.error(f"Catch-up failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/quick")
async def quick_catch_up(query: str):
    """Quick catch-up with natural language query."""
    days_back = 7
    q = query.lower()

    if "today" in q:
        days_back = 1
    elif "yesterday" in q:
        days_back = 2
    elif "this week" in q:
        days_back = 7
    elif "last week" in q:
        days_back = 14
    elif "this month" in q:
        days_back = 30

    context = await gather_context(query, days_back)
    summarizer = Summarizer()
    summary = await summarizer.summarize(context, style="summary")

    return {
        "query": query,
        "summary": summary,
        "items_found": sum(context.total_sources.values()),
        "sources": context.total_sources,
    }


class MorningBriefResponse(BaseModel):
    """Response with morning briefing."""
    date: str
    meetings_today: list[dict[str, Any]]
    key_topics: list[str]
    briefing: str
    generated_at: datetime


@router.get("/morning", response_model=MorningBriefResponse)
async def morning_briefing():
    """Generate a morning briefing with today's schedule and context."""
    import json
    from sqlalchemy import select
    from jarvis_server.calendar.models import CalendarEvent
    from jarvis_server.db.session import AsyncSessionLocal

    today = datetime.utcnow().date()
    logger.info(f"Generating morning briefing for {today}")

    try:
        # Get today's calendar events from database
        start_of_day = datetime.combine(today, datetime.min.time())
        end_of_day = datetime.combine(today, datetime.max.time())

        async with AsyncSessionLocal() as db:
            query = select(CalendarEvent).where(
                CalendarEvent.start_time >= start_of_day,
                CalendarEvent.start_time <= end_of_day,
            ).order_by(CalendarEvent.start_time)
            result = await db.execute(query)
            events = result.scalars().all()

        meetings = []
        key_topics = set()

        for event in events:
            attendees = json.loads(event.attendees_json) if event.attendees_json else []
            meetings.append({
                "time": event.start_time.strftime("%H:%M") if event.start_time else "All day",
                "title": event.summary or "Untitled",
                "attendees": [a.get("email", "") for a in attendees],
            })
            # Extract topics from meeting titles
            if event.summary:
                words = event.summary.split()
                if words:
                    key_topics.add(words[0])

        # Gather context on key topics
        context_items = []
        for topic in list(key_topics)[:3]:  # Limit to top 3 topics
            if topic:
                ctx = await gather_context(topic, days_back=7)
                context_items.extend(ctx.items[:5])  # Top 5 items per topic

        # Build combined context
        combined_context = GatheredContext(
            topic="morning briefing",
            timeframe_start=datetime.utcnow() - timedelta(days=7),
            timeframe_end=datetime.utcnow(),
            items=context_items,
            total_sources={},
        )

        # Generate briefing
        summarizer = Summarizer()
        if meetings:
            meeting_list = "\n".join(
                f"- {m['time']}: {m['title']}" for m in meetings
            )
            briefing = await summarizer.summarize(
                combined_context,
                style="summary",
            )
            briefing = f"**Today's Schedule:**\n{meeting_list}\n\n**Context:**\n{briefing}"
        else:
            briefing = "No meetings scheduled for today. "
            if context_items:
                briefing += await summarizer.summarize(combined_context, style="summary")
            else:
                briefing += "No recent activity to summarize."

        return MorningBriefResponse(
            date=today.isoformat(),
            meetings_today=meetings,
            key_topics=list(key_topics),
            briefing=briefing,
            generated_at=datetime.utcnow(),
        )

    except Exception as e:
        logger.error(f"Morning briefing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
