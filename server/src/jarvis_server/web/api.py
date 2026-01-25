"""Web API endpoints for HTMX fragments.

Returns HTML fragments for dynamic loading in the web UI.
"""

import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.calendar.models import CalendarEvent, Meeting
from jarvis_server.db.models import Capture
from jarvis_server.db.session import get_db
from jarvis_server.search.hybrid import hybrid_search
from jarvis_server.search.schemas import SearchRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/web", tags=["web-api"])

# Templates directory
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=templates_dir)


def highlight_query(text: str, query: str) -> Markup:
    """Highlight search query terms in text.

    Args:
        text: The text to highlight in
        query: The search query (may contain multiple words)

    Returns:
        Markup with highlighted terms
    """
    if not query or not text:
        return Markup(escape(text))

    # Escape the text first to prevent XSS
    escaped_text = str(escape(text))

    # Split query into words and create pattern
    words = [re.escape(word) for word in query.split() if word.strip()]
    if not words:
        return Markup(escaped_text)

    # Create pattern matching any of the query words (case-insensitive)
    pattern = re.compile(f"({'|'.join(words)})", re.IGNORECASE)

    # Replace matches with highlighted spans
    highlighted = pattern.sub(
        r'<mark class="bg-yellow-200 px-0.5 rounded">\1</mark>',
        escaped_text,
    )

    return Markup(highlighted)


# Register the filter with Jinja2
templates.env.filters["highlight_query"] = highlight_query


@router.get("/stats", response_class=HTMLResponse)
async def get_stats(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Get dashboard stats as HTML fragment."""
    # Count total captures
    captures_result = await session.execute(select(func.count(Capture.id)))
    total_captures = captures_result.scalar() or 0

    # Count today's captures
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_captures_result = await session.execute(
        select(func.count(Capture.id)).where(Capture.timestamp >= today_start)
    )
    today_captures = today_captures_result.scalar() or 0

    # Count calendar events
    events_result = await session.execute(select(func.count(CalendarEvent.id)))
    total_events = events_result.scalar() or 0

    # Count meetings with recordings
    meetings_result = await session.execute(
        select(func.count(Meeting.id)).where(Meeting.transcript.isnot(None))
    )
    meetings_with_transcripts = meetings_result.scalar() or 0

    return templates.TemplateResponse(
        request=request,
        name="partials/stats.html",
        context={
            "total_captures": total_captures,
            "today_captures": today_captures,
            "total_events": total_events,
            "meetings_with_transcripts": meetings_with_transcripts,
        },
    )


@router.get("/upcoming-meetings", response_class=HTMLResponse)
async def get_upcoming_meetings(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Get upcoming meetings as HTML fragment."""
    now = datetime.now()
    next_week = now + timedelta(days=7)

    # Get upcoming calendar events
    result = await session.execute(
        select(CalendarEvent)
        .where(CalendarEvent.start_time >= now)
        .where(CalendarEvent.start_time <= next_week)
        .order_by(CalendarEvent.start_time)
        .limit(5)
    )
    events = result.scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="partials/upcoming-meetings.html",
        context={"events": events},
    )


@router.get("/recent-captures", response_class=HTMLResponse)
async def get_recent_captures(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Get recent captures as HTML fragment."""
    # Get last 6 captures
    result = await session.execute(
        select(Capture).order_by(Capture.timestamp.desc()).limit(6)
    )
    captures = result.scalars().all()

    return templates.TemplateResponse(
        request=request,
        name="partials/recent-captures.html",
        context={"captures": captures},
    )


@router.get("/search", response_class=HTMLResponse)
async def search_web(
    request: Request,
    q: str = Query("", description="Search query"),
    sources: Optional[list[str]] = Query(None, description="Source filters"),
    date_range: str = Query("", description="Date range filter"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
) -> HTMLResponse:
    """Search memories and return HTML fragment.

    Args:
        request: FastAPI request
        q: Search query string
        sources: List of sources to filter (screen, chatgpt, claude, grok, email)
        date_range: Date range filter (today, 7d, 30d, 90d, or empty for all)
        limit: Maximum results to return

    Returns:
        HTML fragment with search results
    """
    # Return empty state if no query
    if not q.strip():
        return templates.TemplateResponse(
            request=request,
            name="partials/search-results.html",
            context={
                "results": [],
                "total": 0,
                "query": "",
                "sources": sources,
            },
        )

    # Calculate date range
    start_date = None
    if date_range == "today":
        start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    elif date_range == "7d":
        start_date = datetime.now() - timedelta(days=7)
    elif date_range == "30d":
        start_date = datetime.now() - timedelta(days=30)
    elif date_range == "90d":
        start_date = datetime.now() - timedelta(days=90)

    # Build search request
    search_request = SearchRequest(
        query=q.strip(),
        limit=limit,
        start_date=start_date,
        sources=sources if sources else None,
    )

    try:
        # Perform hybrid search
        results = hybrid_search(search_request)

        return templates.TemplateResponse(
            request=request,
            name="partials/search-results.html",
            context={
                "results": results,
                "total": len(results),
                "query": q.strip(),
                "sources": sources,
            },
        )
    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        return templates.TemplateResponse(
            request=request,
            name="partials/search-results.html",
            context={
                "results": [],
                "total": 0,
                "query": q.strip(),
                "sources": sources,
                "error": "Search failed. Please try again.",
            },
        )
