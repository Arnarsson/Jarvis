"""Web API endpoints for HTMX fragments.

Returns HTML fragments for dynamic loading in the web UI.
"""

import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape
from sqlalchemy import and_, func, select
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


@router.get("/timeline/grid", response_class=HTMLResponse)
async def get_timeline_grid(
    request: Request,
    session: AsyncSession = Depends(get_db),
    date_param: date = Query(alias="date", description="Date to load captures for"),
    cursor: Optional[str] = Query(None, description="Pagination cursor (ISO timestamp)"),
    limit: int = Query(50, ge=1, le=200, description="Number of captures to return"),
) -> HTMLResponse:
    """Get capture grid for a specific date.

    Returns HTML fragment with capture thumbnails for the selected date.
    Uses cursor-based pagination for infinite scroll.
    """
    # Build query conditions
    conditions = [
        Capture.timestamp >= datetime.combine(date_param, datetime.min.time()),
        Capture.timestamp <= datetime.combine(date_param, datetime.max.time()),
    ]

    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
            conditions.append(Capture.timestamp < cursor_dt)
        except ValueError:
            pass

    # Query captures
    query = (
        select(Capture)
        .where(and_(*conditions))
        .order_by(Capture.timestamp.desc())
        .limit(limit + 1)
    )

    result = await session.execute(query)
    captures = list(result.scalars().all())

    # Check for more results
    has_more = len(captures) > limit
    if has_more:
        captures = captures[:limit]

    # Get total count for the date
    count_query = select(func.count(Capture.id)).where(
        and_(
            Capture.timestamp >= datetime.combine(date_param, datetime.min.time()),
            Capture.timestamp <= datetime.combine(date_param, datetime.max.time()),
        )
    )
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Determine next cursor
    next_cursor = None
    if has_more and captures:
        next_cursor = captures[-1].timestamp.isoformat()

    # Transform captures for template
    capture_data = [
        {
            "id": c.id,
            "timestamp": c.timestamp,
            "filepath": c.filepath,
            "width": c.width,
            "height": c.height,
            "has_ocr": bool(c.ocr_text),
            "text_preview": c.ocr_text[:100] if c.ocr_text else None,
        }
        for c in captures
    ]

    return templates.TemplateResponse(
        request=request,
        name="partials/capture-grid.html",
        context={
            "captures": capture_data,
            "total": total,
            "has_more": has_more,
            "next_cursor": next_cursor,
            "selected_date": date_param.isoformat(),
        },
    )


@router.get("/timeline/capture/{capture_id}", response_class=HTMLResponse)
async def get_capture_modal(
    request: Request,
    capture_id: str,
    session: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Get capture detail modal.

    Returns HTML fragment with full capture details and OCR text.
    Includes navigation to previous/next captures.
    """
    from fastapi import HTTPException

    # Get the capture
    result = await session.execute(
        select(Capture).where(Capture.id == capture_id)
    )
    capture = result.scalar_one_or_none()

    if not capture:
        raise HTTPException(status_code=404, detail="Capture not found")

    # Get previous capture (newer)
    prev_result = await session.execute(
        select(Capture.id)
        .where(Capture.timestamp > capture.timestamp)
        .order_by(Capture.timestamp.asc())
        .limit(1)
    )
    prev_capture = prev_result.scalar()

    # Get next capture (older)
    next_result = await session.execute(
        select(Capture.id)
        .where(Capture.timestamp < capture.timestamp)
        .order_by(Capture.timestamp.desc())
        .limit(1)
    )
    next_capture = next_result.scalar()

    return templates.TemplateResponse(
        request=request,
        name="partials/capture-modal.html",
        context={
            "capture": capture,
            "prev_capture": prev_capture,
            "next_capture": next_capture,
        },
    )


@router.get("/result/{result_id}", response_class=HTMLResponse)
async def get_result_detail(
    request: Request,
    result_id: str,
    source: str = Query(..., description="Result source type"),
    session: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Get result detail for modal display.

    Args:
        request: FastAPI request
        result_id: ID of the result to display
        source: Source type (screen, chatgpt, claude, grok, email)
        session: Database session

    Returns:
        HTML fragment with result details
    """
    from fastapi import HTTPException

    context: dict = {"result": None, "email": None, "conversation_id": None}

    if source == "screen":
        # Load capture from database
        result = await session.execute(
            select(Capture).where(Capture.id == result_id)
        )
        capture = result.scalar_one_or_none()

        if not capture:
            raise HTTPException(status_code=404, detail="Capture not found")

        context["result"] = {
            "id": capture.id,
            "source": "screen",
            "timestamp": capture.timestamp,
            "filepath": capture.filepath,
            "text_preview": capture.ocr_text or "No OCR text available",
            "score": None,
        }

    elif source == "email":
        # Load email from database
        from jarvis_server.email.models import Email

        result = await session.execute(
            select(Email).where(Email.id == result_id)
        )
        email = result.scalar_one_or_none()

        if not email:
            raise HTTPException(status_code=404, detail="Email not found")

        context["result"] = {
            "id": email.id,
            "source": "email",
            "timestamp": email.received_at,
            "filepath": None,
            "text_preview": f"Email: {email.subject}\nFrom: {email.sender}",
            "score": None,
        }
        context["email"] = email

    elif source in ["chatgpt", "claude", "grok"]:
        # Load conversation from database
        from jarvis_server.chat.models import Conversation

        result = await session.execute(
            select(Conversation).where(Conversation.id == result_id)
        )
        conversation = result.scalar_one_or_none()

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        context["result"] = {
            "id": conversation.id,
            "source": source,
            "timestamp": conversation.created_at,
            "filepath": None,
            "text_preview": conversation.text_content or "No content available",
            "score": None,
        }
        context["conversation_id"] = conversation.external_id

    else:
        raise HTTPException(status_code=400, detail=f"Unknown source type: {source}")

    return templates.TemplateResponse(
        request=request,
        name="partials/result-modal.html",
        context=context,
    )
