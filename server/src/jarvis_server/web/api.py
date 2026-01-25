"""Web API endpoints for HTMX fragments.

Returns HTML fragments for dynamic loading in the web UI.
"""

import calendar as cal_module
import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import markdown
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


# --- Calendar Endpoints ---


def _get_initials(email: str) -> str:
    """Extract initials from email address."""
    local_part = email.split("@")[0]
    # Try to split on common separators
    parts = re.split(r"[._-]", local_part)
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    # Fallback to first two chars
    return local_part[:2].upper()


def _parse_attendees(attendees_json: str | None) -> list[dict]:
    """Parse attendees JSON and add computed fields."""
    if not attendees_json:
        return []
    try:
        attendees = json.loads(attendees_json)
        for attendee in attendees:
            email = attendee.get("email", "")
            attendee["initials"] = _get_initials(email)
            # Use displayName if available, otherwise email
            attendee["display_name"] = attendee.get("displayName") or email
            # Normalize response status
            status = attendee.get("responseStatus", "needsAction")
            attendee["response_status"] = status
            attendee["organizer"] = attendee.get("organizer", False)
        return attendees
    except (json.JSONDecodeError, TypeError):
        return []


def _calculate_duration(start: datetime, end: datetime) -> str:
    """Calculate human-readable duration string."""
    duration = end - start
    total_minutes = int(duration.total_seconds() / 60)

    if total_minutes < 60:
        return f"{total_minutes}min"
    hours = total_minutes // 60
    minutes = total_minutes % 60
    if minutes == 0:
        return f"{hours}hr"
    return f"{hours}hr {minutes}min"


@router.get("/calendar/month", response_class=HTMLResponse)
async def get_calendar_month(
    request: Request,
    year: Optional[int] = Query(None, description="Year"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Month (1-12)"),
    session: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Get calendar month grid as HTML fragment.

    Args:
        request: FastAPI request
        year: Year to display (defaults to current year)
        month: Month to display (defaults to current month)
        session: Database session

    Returns:
        HTML fragment with month calendar grid
    """
    # Default to current month
    today = date.today()
    year = year or today.year
    month = month or today.month

    # Calculate prev/next month
    if month == 1:
        prev_year, prev_month = year - 1, 12
    else:
        prev_year, prev_month = year, month - 1

    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    # Get month name
    month_name = cal_module.month_name[month]

    # Get calendar weeks (Monday start)
    cal = cal_module.Calendar(firstweekday=0)  # Monday = 0
    month_days = cal.monthdatescalendar(year, month)

    # Get all events for this month with a margin
    first_day = month_days[0][0]
    last_day = month_days[-1][-1]

    start_dt = datetime.combine(first_day, datetime.min.time())
    end_dt = datetime.combine(last_day, datetime.max.time())

    result = await session.execute(
        select(CalendarEvent)
        .where(CalendarEvent.start_time >= start_dt)
        .where(CalendarEvent.start_time <= end_dt)
        .order_by(CalendarEvent.start_time)
    )
    events = result.scalars().all()

    # Group events by date
    events_by_date: dict[date, list] = {}
    for event in events:
        event_date = event.start_time.date()
        if event_date not in events_by_date:
            events_by_date[event_date] = []
        events_by_date[event_date].append({
            "id": event.id,
            "summary": event.summary,
            "start_time": event.start_time,
        })

    # Build weeks data
    weeks = []
    for week in month_days:
        week_data = []
        for day_date in week:
            is_current_month = day_date.month == month
            is_today = day_date == today
            day_events = events_by_date.get(day_date, [])

            # Format label for display
            label = day_date.strftime("%A, %B %d, %Y")

            week_data.append({
                "day": day_date.day,
                "date": day_date.isoformat(),
                "label": label,
                "is_current_month": is_current_month,
                "is_today": is_today,
                "has_events": len(day_events) > 0,
                "event_count": len(day_events),
                "events": day_events,
            })
        weeks.append(week_data)

    return templates.TemplateResponse(
        request=request,
        name="partials/calendar-grid.html",
        context={
            "year": year,
            "month": month,
            "month_name": month_name,
            "prev_year": prev_year,
            "prev_month": prev_month,
            "next_year": next_year,
            "next_month": next_month,
            "weeks": weeks,
            "today": today,
        },
    )


@router.get("/calendar/events", response_class=HTMLResponse)
async def get_calendar_events(
    request: Request,
    event_date: date = Query(alias="date", description="Date to load events for"),
    session: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Get events for a specific date as HTML fragment.

    Args:
        request: FastAPI request
        event_date: Date to load events for
        session: Database session

    Returns:
        HTML fragment with events list
    """
    start_dt = datetime.combine(event_date, datetime.min.time())
    end_dt = datetime.combine(event_date, datetime.max.time())

    result = await session.execute(
        select(CalendarEvent)
        .where(CalendarEvent.start_time >= start_dt)
        .where(CalendarEvent.start_time <= end_dt)
        .order_by(CalendarEvent.start_time)
    )
    db_events = result.scalars().all()

    # Transform events for template
    events = []
    for event in db_events:
        duration_str = _calculate_duration(event.start_time, event.end_time)
        attendees = _parse_attendees(event.attendees_json)

        events.append({
            "id": event.id,
            "summary": event.summary,
            "start_time": event.start_time,
            "end_time": event.end_time,
            "duration_str": duration_str,
            "location": event.location,
            "meeting_link": event.meeting_link,
            "attendees": attendees,
        })

    return templates.TemplateResponse(
        request=request,
        name="partials/events-list.html",
        context={
            "events": events,
            "date": event_date,
        },
    )


@router.get("/calendar/upcoming-briefs", response_class=HTMLResponse)
async def get_upcoming_briefs(
    request: Request,
    hours: int = Query(24, ge=1, le=168, description="Hours to look ahead"),
    session: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Get upcoming meetings with briefs as HTML fragment.

    Args:
        request: FastAPI request
        hours: Number of hours to look ahead (default 24)
        session: Database session

    Returns:
        HTML fragment with upcoming meetings and brief status
    """
    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=hours)

    result = await session.execute(
        select(CalendarEvent)
        .where(CalendarEvent.start_time >= now)
        .where(CalendarEvent.start_time <= end)
        .order_by(CalendarEvent.start_time)
        .limit(10)
    )
    db_events = result.scalars().all()

    # Check for existing briefs (via Meeting model)
    events_with_brief_status = []
    for event in db_events:
        # Check if there's a meeting with a brief for this event
        meeting_result = await session.execute(
            select(Meeting)
            .where(Meeting.calendar_event_id == event.id)
            .limit(1)
        )
        meeting = meeting_result.scalar_one_or_none()
        has_brief = meeting is not None and meeting.brief is not None

        duration_str = _calculate_duration(event.start_time, event.end_time)

        events_with_brief_status.append({
            "id": event.id,
            "summary": event.summary,
            "start_time": event.start_time,
            "duration_str": duration_str,
            "meeting_link": event.meeting_link,
            "has_brief": has_brief,
            "is_soon": (event.start_time - now).total_seconds() < 3600,  # Within 1 hour
        })

    return templates.TemplateResponse(
        request=request,
        name="partials/upcoming-briefs.html",
        context={
            "events": events_with_brief_status,
        },
    )


@router.get("/meetings/brief/{event_id}", response_class=HTMLResponse)
async def get_meeting_brief(
    request: Request,
    event_id: str,
    session: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Get meeting brief for an event as HTML fragment.

    Args:
        request: FastAPI request
        event_id: Calendar event ID
        session: Database session

    Returns:
        HTML fragment with meeting brief or generate button
    """
    from fastapi import HTTPException

    # Get the calendar event
    event_result = await session.execute(
        select(CalendarEvent).where(CalendarEvent.id == event_id)
    )
    event = event_result.scalar_one_or_none()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Check for existing meeting with brief
    meeting_result = await session.execute(
        select(Meeting)
        .where(Meeting.calendar_event_id == event_id)
        .limit(1)
    )
    meeting = meeting_result.scalar_one_or_none()

    # Parse attendees
    attendees = _parse_attendees(event.attendees_json)

    # Build event context
    event_context = {
        "id": event.id,
        "summary": event.summary,
        "start_time": event.start_time,
        "end_time": event.end_time,
        "location": event.location,
        "meeting_link": event.meeting_link,
        "attendees": attendees,
    }

    if meeting and meeting.brief:
        # Convert brief markdown to HTML
        brief_html = markdown.markdown(
            meeting.brief,
            extensions=["extra", "nl2br"],
        )

        return templates.TemplateResponse(
            request=request,
            name="partials/meeting-brief.html",
            context={
                "event": event_context,
                "brief": meeting.brief,
                "brief_html": brief_html,
                "was_cached": True,
                "needs_generation": False,
            },
        )
    else:
        return templates.TemplateResponse(
            request=request,
            name="partials/meeting-brief.html",
            context={
                "event": event_context,
                "brief": None,
                "needs_generation": True,
            },
        )


@router.post("/meetings/brief/{event_id}", response_class=HTMLResponse)
async def generate_meeting_brief(
    request: Request,
    event_id: str,
    force_regenerate: bool = Query(False, description="Force regeneration"),
    session: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Generate meeting brief for an event.

    Args:
        request: FastAPI request
        event_id: Calendar event ID
        force_regenerate: Whether to regenerate even if cached
        session: Database session

    Returns:
        HTML fragment with generated brief
    """
    from fastapi import HTTPException
    from jarvis_server.meetings.briefs import get_or_generate_brief

    # Get the calendar event
    event_result = await session.execute(
        select(CalendarEvent).where(CalendarEvent.id == event_id)
    )
    event = event_result.scalar_one_or_none()

    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    try:
        brief, was_generated = await get_or_generate_brief(
            event_id, session, force_regenerate
        )

        # Parse attendees
        attendees = _parse_attendees(event.attendees_json)

        # Build event context
        event_context = {
            "id": event.id,
            "summary": event.summary,
            "start_time": event.start_time,
            "end_time": event.end_time,
            "location": event.location,
            "meeting_link": event.meeting_link,
            "attendees": attendees,
        }

        # Convert brief markdown to HTML
        brief_html = markdown.markdown(
            brief,
            extensions=["extra", "nl2br"],
        )

        return templates.TemplateResponse(
            request=request,
            name="partials/meeting-brief.html",
            context={
                "event": event_context,
                "brief": brief,
                "brief_html": brief_html,
                "was_cached": not was_generated,
                "needs_generation": False,
            },
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Brief generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate brief")


# --- Settings Endpoints ---


def _format_bytes(size_bytes: int) -> str:
    """Format bytes as human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def _get_dir_size(path: Path) -> int:
    """Calculate total size of directory in bytes."""
    total = 0
    try:
        if path.exists() and path.is_dir():
            for f in path.rglob("*"):
                if f.is_file():
                    total += f.stat().st_size
    except Exception:
        pass
    return total


@router.get("/settings/status", response_class=HTMLResponse)
async def get_settings_status(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Get system status as HTML fragment.

    Checks health of all services: Server, PostgreSQL, Redis, Qdrant.
    Returns status cards partial with current status and stats.
    """
    from datetime import datetime, timezone

    import redis
    from qdrant_client import QdrantClient
    from sqlalchemy import text

    from jarvis_server import __version__
    from jarvis_server.config import get_settings

    settings = get_settings()

    # Server status
    server_status = {"status": "healthy", "version": __version__}

    # PostgreSQL status
    postgres_status = {"status": "unknown", "captures_count": 0}
    try:
        await session.execute(text("SELECT 1"))
        # Count captures
        result = await session.execute(select(func.count(Capture.id)))
        captures_count = result.scalar() or 0
        postgres_status = {"status": "healthy", "captures_count": captures_count}
    except Exception as e:
        logger.warning(f"PostgreSQL health check failed: {e}")
        postgres_status = {"status": "unhealthy", "captures_count": 0}
        server_status["status"] = "degraded"

    # Redis status
    redis_status = {"status": "unknown"}
    try:
        r = redis.Redis(host=settings.redis_host, port=settings.redis_port)
        r.ping()
        redis_status = {"status": "healthy"}
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        redis_status = {"status": "unhealthy"}
        server_status["status"] = "degraded"

    # Qdrant status
    qdrant_status = {"status": "unknown", "vectors_count": 0}
    try:
        client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        collection_info = client.get_collection("captures")
        vectors_count = collection_info.points_count or 0
        qdrant_status = {"status": "healthy", "vectors_count": vectors_count}
    except Exception as e:
        logger.warning(f"Qdrant health check failed: {e}")
        qdrant_status = {"status": "unhealthy", "vectors_count": 0}
        server_status["status"] = "degraded"

    # Storage stats
    storage_path = settings.storage_path
    storage_size = _get_dir_size(storage_path)
    storage_status = {
        "used_bytes": storage_size,
        "used_formatted": _format_bytes(storage_size),
        "used_percent": min(100, int(storage_size / (100 * 1024 * 1024 * 1024) * 100)),  # Assume 100GB max
        "captures_count": postgres_status["captures_count"],
        "path": str(storage_path),
    }

    return templates.TemplateResponse(
        request=request,
        name="partials/status-cards.html",
        context={
            "server": server_status,
            "postgres": postgres_status,
            "redis": redis_status,
            "qdrant": qdrant_status,
            "storage": storage_status,
            "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        },
    )


@router.get("/settings/integrations", response_class=HTMLResponse)
async def get_settings_integrations(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Get integration settings as HTML fragment.

    Shows status of Google Calendar, Gmail, and conversation imports.
    """
    from jarvis_server.calendar.models import CalendarEvent, SyncState
    from jarvis_server.calendar.oauth import credentials_exist as calendar_credentials_exist
    from jarvis_server.calendar.oauth import is_authenticated as calendar_is_authenticated
    from jarvis_server.db.models import ConversationRecord
    from jarvis_server.email.models import EmailMessage, EmailSyncState
    from jarvis_server.email.oauth import credentials_exist as gmail_credentials_exist
    from jarvis_server.email.oauth import is_authenticated as gmail_is_authenticated

    # Google Calendar status
    calendar_authenticated = calendar_is_authenticated()
    calendar_events_count = 0
    calendar_last_sync = None

    if calendar_authenticated:
        # Count events
        result = await session.execute(select(func.count(CalendarEvent.id)))
        calendar_events_count = result.scalar() or 0

        # Get last sync time
        sync_result = await session.execute(
            select(SyncState).where(SyncState.id == "calendar_primary")
        )
        sync_state = sync_result.scalar_one_or_none()
        if sync_state:
            # SyncState only stores token, get most recent event sync time
            event_result = await session.execute(
                select(CalendarEvent.synced_at)
                .order_by(CalendarEvent.synced_at.desc())
                .limit(1)
            )
            last_synced = event_result.scalar()
            if last_synced:
                calendar_last_sync = last_synced.strftime("%Y-%m-%d %H:%M")

    calendar_status = {
        "authenticated": calendar_authenticated,
        "credentials_exist": calendar_credentials_exist(),
        "events_count": calendar_events_count,
        "last_sync": calendar_last_sync,
    }

    # Gmail status
    gmail_authenticated = gmail_is_authenticated()
    gmail_emails_count = 0
    gmail_last_sync = None

    if gmail_authenticated:
        # Count emails
        result = await session.execute(select(func.count(EmailMessage.id)))
        gmail_emails_count = result.scalar() or 0

        # Get last sync time
        sync_result = await session.execute(
            select(EmailSyncState).where(EmailSyncState.id == "gmail_primary")
        )
        sync_state = sync_result.scalar_one_or_none()
        if sync_state and hasattr(sync_state, "updated_at"):
            gmail_last_sync = sync_state.updated_at.strftime("%Y-%m-%d %H:%M")

    gmail_status = {
        "authenticated": gmail_authenticated,
        "credentials_exist": gmail_credentials_exist(),
        "emails_count": gmail_emails_count,
        "last_sync": gmail_last_sync,
    }

    # Conversations count
    conversations_result = await session.execute(select(func.count(ConversationRecord.id)))
    conversations_count = conversations_result.scalar() or 0

    conversations_status = {
        "count": conversations_count,
    }

    return templates.TemplateResponse(
        request=request,
        name="partials/integration-settings.html",
        context={
            "calendar": calendar_status,
            "gmail": gmail_status,
            "conversations": conversations_status,
            "sync_result": None,
        },
    )


@router.post("/settings/calendar/sync", response_class=HTMLResponse)
async def trigger_calendar_sync(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Trigger calendar sync and return updated integrations status.

    Performs a calendar sync and returns the integration settings partial
    with a success message.
    """
    from jarvis_server.calendar.oauth import CalendarAuthRequired
    from jarvis_server.calendar.sync import sync_calendar

    sync_result_msg = None

    try:
        result = await sync_calendar(session)
        created = result.get("created", 0)
        updated = result.get("updated", 0)
        deleted = result.get("deleted", 0)
        sync_result_msg = f"Calendar synced: {created} created, {updated} updated, {deleted} deleted"
    except CalendarAuthRequired:
        sync_result_msg = "Calendar sync failed: authentication required"
    except Exception as e:
        logger.error(f"Calendar sync failed: {e}", exc_info=True)
        sync_result_msg = f"Calendar sync failed: {str(e)[:50]}"

    # Return updated integrations partial
    return await _get_integrations_with_result(request, session, sync_result_msg)


@router.post("/settings/gmail/sync", response_class=HTMLResponse)
async def trigger_gmail_sync(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """Trigger Gmail sync and return updated integrations status.

    Performs an email sync and returns the integration settings partial
    with a success message.
    """
    from jarvis_server.email.oauth import GmailAuthRequired
    from jarvis_server.email.sync import sync_emails

    sync_result_msg = None

    try:
        result = await sync_emails(session)
        created = result.get("created", 0)
        updated = result.get("updated", 0)
        deleted = result.get("deleted", 0)
        sync_result_msg = f"Gmail synced: {created} created, {updated} updated, {deleted} deleted"
    except GmailAuthRequired:
        sync_result_msg = "Gmail sync failed: authentication required"
    except Exception as e:
        logger.error(f"Gmail sync failed: {e}", exc_info=True)
        sync_result_msg = f"Gmail sync failed: {str(e)[:50]}"

    # Return updated integrations partial
    return await _get_integrations_with_result(request, session, sync_result_msg)


async def _get_integrations_with_result(
    request: Request,
    session: AsyncSession,
    sync_result_msg: str | None,
) -> HTMLResponse:
    """Helper to get integrations partial with a sync result message."""
    from jarvis_server.calendar.models import CalendarEvent, SyncState
    from jarvis_server.calendar.oauth import credentials_exist as calendar_credentials_exist
    from jarvis_server.calendar.oauth import is_authenticated as calendar_is_authenticated
    from jarvis_server.db.models import ConversationRecord
    from jarvis_server.email.models import EmailMessage, EmailSyncState
    from jarvis_server.email.oauth import credentials_exist as gmail_credentials_exist
    from jarvis_server.email.oauth import is_authenticated as gmail_is_authenticated

    # Calendar status
    calendar_authenticated = calendar_is_authenticated()
    calendar_events_count = 0
    calendar_last_sync = None

    if calendar_authenticated:
        result = await session.execute(select(func.count(CalendarEvent.id)))
        calendar_events_count = result.scalar() or 0
        event_result = await session.execute(
            select(CalendarEvent.synced_at)
            .order_by(CalendarEvent.synced_at.desc())
            .limit(1)
        )
        last_synced = event_result.scalar()
        if last_synced:
            calendar_last_sync = last_synced.strftime("%Y-%m-%d %H:%M")

    # Gmail status
    gmail_authenticated = gmail_is_authenticated()
    gmail_emails_count = 0
    gmail_last_sync = None

    if gmail_authenticated:
        result = await session.execute(select(func.count(EmailMessage.id)))
        gmail_emails_count = result.scalar() or 0
        sync_result = await session.execute(
            select(EmailSyncState).where(EmailSyncState.id == "gmail_primary")
        )
        sync_state = sync_result.scalar_one_or_none()
        if sync_state and hasattr(sync_state, "updated_at"):
            gmail_last_sync = sync_state.updated_at.strftime("%Y-%m-%d %H:%M")

    # Conversations count
    conversations_result = await session.execute(select(func.count(ConversationRecord.id)))
    conversations_count = conversations_result.scalar() or 0

    return templates.TemplateResponse(
        request=request,
        name="partials/integration-settings.html",
        context={
            "calendar": {
                "authenticated": calendar_authenticated,
                "credentials_exist": calendar_credentials_exist(),
                "events_count": calendar_events_count,
                "last_sync": calendar_last_sync,
            },
            "gmail": {
                "authenticated": gmail_authenticated,
                "credentials_exist": gmail_credentials_exist(),
                "emails_count": gmail_emails_count,
                "last_sync": gmail_last_sync,
            },
            "conversations": {
                "count": conversations_count,
            },
            "sync_result": sync_result_msg,
        },
    )
