"""Meeting lifecycle API endpoints."""

from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.calendar.models import CalendarEvent, Meeting
from jarvis_server.db.session import get_db_session

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
    db: AsyncSession = Depends(get_db_session),
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
    db: AsyncSession = Depends(get_db_session),
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
    db: AsyncSession = Depends(get_db_session),
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
    db: AsyncSession = Depends(get_db_session),
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
