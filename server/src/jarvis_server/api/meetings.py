"""Meeting lifecycle API endpoints."""

from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.calendar.models import CalendarEvent, Meeting
from jarvis_server.db.session import get_db

router = APIRouter(prefix="/api/meetings", tags=["meetings"])
logger = structlog.get_logger()


class MeetingStartRequest(BaseModel):
    """Request to start a new meeting."""

    platform: str
    window_title: Optional[str] = None
    detected_at: Optional[datetime] = None


class MeetingEndRequest(BaseModel):
    """Request to end a meeting."""

    meeting_id: str
    ended_at: Optional[datetime] = None


class MeetingResponse(BaseModel):
    """Meeting response schema."""

    id: str
    platform: Optional[str]
    detected_at: datetime
    ended_at: Optional[datetime]
    calendar_event_id: Optional[str]
    transcript_status: str
    has_summary: bool


@router.post("/start", response_model=MeetingResponse)
async def start_meeting(
    request: MeetingStartRequest,
    db: AsyncSession = Depends(get_db),
) -> MeetingResponse:
    """Record that a meeting has started.

    Called by the agent when it detects a meeting window.
    Attempts to correlate with a calendar event if one exists around this time.
    """
    detected_at = request.detected_at or datetime.now(timezone.utc)

    # Try to find matching calendar event (within 15 min of start time)
    window_start = detected_at - timedelta(minutes=15)
    window_end = detected_at + timedelta(minutes=15)

    result = await db.execute(
        select(CalendarEvent)
        .where(CalendarEvent.start_time >= window_start)
        .where(CalendarEvent.start_time <= window_end)
        .order_by(CalendarEvent.start_time)
        .limit(1)
    )
    calendar_event = result.scalar_one_or_none()

    meeting = Meeting(
        platform=request.platform,
        detected_at=detected_at,
        calendar_event_id=calendar_event.id if calendar_event else None,
    )
    db.add(meeting)
    await db.commit()
    await db.refresh(meeting)

    logger.info(
        "meeting_started",
        meeting_id=meeting.id,
        platform=request.platform,
        calendar_event_id=meeting.calendar_event_id,
    )

    return MeetingResponse(
        id=meeting.id,
        platform=meeting.platform,
        detected_at=meeting.detected_at,
        ended_at=meeting.ended_at,
        calendar_event_id=meeting.calendar_event_id,
        transcript_status=meeting.transcript_status,
        has_summary=meeting.summary is not None,
    )


@router.post("/end", response_model=MeetingResponse)
async def end_meeting(
    request: MeetingEndRequest,
    db: AsyncSession = Depends(get_db),
) -> MeetingResponse:
    """Record that a meeting has ended."""
    result = await db.execute(select(Meeting).where(Meeting.id == request.meeting_id))
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    meeting.ended_at = request.ended_at or datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(meeting)

    duration = (meeting.ended_at - meeting.detected_at).total_seconds()
    logger.info(
        "meeting_ended",
        meeting_id=meeting.id,
        duration_seconds=duration,
    )

    return MeetingResponse(
        id=meeting.id,
        platform=meeting.platform,
        detected_at=meeting.detected_at,
        ended_at=meeting.ended_at,
        calendar_event_id=meeting.calendar_event_id,
        transcript_status=meeting.transcript_status,
        has_summary=meeting.summary is not None,
    )


@router.get("/current", response_model=Optional[MeetingResponse])
async def get_current_meeting(
    db: AsyncSession = Depends(get_db),
) -> Optional[MeetingResponse]:
    """Get the currently active meeting, if any."""
    result = await db.execute(
        select(Meeting)
        .where(Meeting.ended_at.is_(None))
        .order_by(Meeting.detected_at.desc())
        .limit(1)
    )
    meeting = result.scalar_one_or_none()

    if not meeting:
        return None

    return MeetingResponse(
        id=meeting.id,
        platform=meeting.platform,
        detected_at=meeting.detected_at,
        ended_at=meeting.ended_at,
        calendar_event_id=meeting.calendar_event_id,
        transcript_status=meeting.transcript_status,
        has_summary=meeting.summary is not None,
    )


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    meeting_id: str,
    db: AsyncSession = Depends(get_db),
) -> MeetingResponse:
    """Get meeting by ID."""
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()

    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    return MeetingResponse(
        id=meeting.id,
        platform=meeting.platform,
        detected_at=meeting.detected_at,
        ended_at=meeting.ended_at,
        calendar_event_id=meeting.calendar_event_id,
        transcript_status=meeting.transcript_status,
        has_summary=meeting.summary is not None,
    )


# --- Pre-meeting Brief Endpoints ---


class BriefResponse(BaseModel):
    """Response model for meeting briefs."""

    event_id: str
    event_summary: str
    brief: str
    generated_at: Optional[datetime] = None
    was_cached: bool


@router.post("/brief/{event_id}", response_model=BriefResponse)
async def generate_brief(
    event_id: str,
    force_regenerate: bool = False,
    db: AsyncSession = Depends(get_db)
) -> BriefResponse:
    """Generate or retrieve pre-meeting brief for a calendar event.

    Args:
        event_id: The calendar event ID
        force_regenerate: If True, regenerate even if cached

    Returns:
        Brief response with generated or cached brief text.

    Raises:
        HTTPException 404: If calendar event not found
        HTTPException 500: If brief generation fails
    """
    from jarvis_server.meetings.briefs import get_or_generate_brief

    # Get the event for response
    result = await db.execute(
        select(CalendarEvent).where(CalendarEvent.id == event_id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Calendar event not found")

    try:
        brief, was_generated = await get_or_generate_brief(event_id, db, force_regenerate)

        return BriefResponse(
            event_id=event_id,
            event_summary=event.summary,
            brief=brief,
            generated_at=datetime.now(timezone.utc) if was_generated else None,
            was_cached=not was_generated
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("brief_endpoint_error", event_id=event_id, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to generate brief")


@router.get("/upcoming/briefs", response_model=list[BriefResponse])
async def get_upcoming_briefs(
    hours: int = 24,
    db: AsyncSession = Depends(get_db)
) -> list[BriefResponse]:
    """Get briefs for all meetings in the next N hours.

    Generates briefs on-demand if not cached.

    Args:
        hours: Number of hours to look ahead (default 24, max 168 = 1 week)

    Returns:
        List of briefs for upcoming meetings.
    """
    from jarvis_server.meetings.briefs import get_or_generate_brief

    # Cap hours to 1 week
    hours = min(hours, 168)

    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=hours)

    # Get upcoming events
    result = await db.execute(
        select(CalendarEvent)
        .where(CalendarEvent.start_time >= now)
        .where(CalendarEvent.start_time <= end)
        .order_by(CalendarEvent.start_time)
    )
    events = result.scalars().all()

    briefs = []
    for event in events:
        try:
            brief, was_generated = await get_or_generate_brief(event.id, db)
            briefs.append(BriefResponse(
                event_id=event.id,
                event_summary=event.summary,
                brief=brief,
                generated_at=datetime.now(timezone.utc) if was_generated else None,
                was_cached=not was_generated
            ))
        except Exception as e:
            logger.warning("brief_skipped", event_id=event.id, error=str(e))

    return briefs
