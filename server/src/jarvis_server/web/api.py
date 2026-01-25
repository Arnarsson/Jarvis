"""Web API endpoints for HTMX fragments.

Returns HTML fragments for dynamic loading in the web UI.
"""

from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.calendar.models import CalendarEvent, Meeting
from jarvis_server.db.models import Capture
from jarvis_server.db.session import get_db

router = APIRouter(prefix="/api/web", tags=["web-api"])

# Templates directory
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=templates_dir)


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
