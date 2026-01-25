"""Calendar API endpoints for OAuth, sync, and event access."""

import json
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.calendar.models import CalendarEvent
from jarvis_server.calendar.oauth import (
    CalendarAuthRequired,
    CredentialsNotFound,
    credentials_exist,
    get_calendar_service,
    is_authenticated,
    start_oauth_flow,
)
from jarvis_server.db.session import get_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


class AuthStatusResponse(BaseModel):
    """Response for auth status endpoint."""

    authenticated: bool
    needs_credentials: bool


class AuthStartResponse(BaseModel):
    """Response for auth start endpoint."""

    status: str
    message: str


class CalendarEventResponse(BaseModel):
    """Response model for a calendar event."""

    id: str
    summary: str
    start: str
    end: str
    location: str | None = None
    description: str | None = None
    meeting_link: str | None = None
    attendees: list[str] = []


class UpcomingEventsResponse(BaseModel):
    """Response for upcoming events endpoint."""

    events: list[CalendarEventResponse]
    count: int


class SyncResponse(BaseModel):
    """Response for sync endpoint."""

    status: str
    job_id: str | None = None
    created: int | None = None
    updated: int | None = None
    deleted: int | None = None


class StoredEventResponse(BaseModel):
    """Response model for a stored calendar event."""

    id: str
    summary: str
    start_time: str
    end_time: str
    location: str | None = None
    meeting_link: str | None = None
    attendees: list[dict] = []


@router.get("/auth/status", response_model=AuthStatusResponse)
async def get_auth_status() -> AuthStatusResponse:
    """Check Google Calendar authentication status.

    Returns:
        Authentication status including whether credentials file exists.
    """
    return AuthStatusResponse(
        authenticated=is_authenticated(),
        needs_credentials=not credentials_exist(),
    )


@router.post("/auth/start", response_model=AuthStartResponse)
async def start_auth() -> AuthStartResponse:
    """Start Google Calendar OAuth flow.

    This endpoint initiates the OAuth flow. The user must complete
    authentication in their browser. This works when the server
    is running on the same machine as the user's browser.

    Returns:
        Status message about authentication flow.

    Raises:
        HTTPException: If credentials.json is missing.
    """
    try:
        message = start_oauth_flow()
        logger.info("calendar_oauth_completed")
        return AuthStartResponse(status="auth_completed", message=message)
    except CredentialsNotFound as e:
        logger.warning("calendar_credentials_not_found")
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e


@router.get("/events/upcoming", response_model=UpcomingEventsResponse)
async def get_upcoming_events(limit: int = 10) -> UpcomingEventsResponse:
    """Get upcoming calendar events.

    Args:
        limit: Maximum number of events to return (default 10, max 50).

    Returns:
        List of upcoming events from primary calendar.

    Raises:
        HTTPException: If authentication is required.
    """
    # Cap the limit
    limit = min(limit, 50)

    try:
        service = get_calendar_service()
    except CalendarAuthRequired as e:
        raise HTTPException(
            status_code=401,
            detail=str(e),
        ) from e

    try:
        # Get events starting from now
        now = datetime.now(timezone.utc).isoformat()

        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=now,
                maxResults=limit,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = events_result.get("items", [])
        logger.info("calendar_events_fetched", count=len(events))

        # Transform to response model
        response_events = []
        for event in events:
            # Handle all-day events (date) vs timed events (dateTime)
            start = event["start"].get("dateTime", event["start"].get("date", ""))
            end = event["end"].get("dateTime", event["end"].get("date", ""))

            # Extract meeting link if present
            meeting_link = _extract_meeting_link(event)

            # Extract attendee emails
            attendees = [
                a.get("email", "")
                for a in event.get("attendees", [])
                if a.get("email")
            ]

            response_events.append(
                CalendarEventResponse(
                    id=event["id"],
                    summary=event.get("summary", "(No title)"),
                    start=start,
                    end=end,
                    location=event.get("location"),
                    description=event.get("description"),
                    meeting_link=meeting_link,
                    attendees=attendees,
                )
            )

        return UpcomingEventsResponse(events=response_events, count=len(response_events))

    except Exception as e:
        logger.error("calendar_events_fetch_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch calendar events: {e}",
        ) from e


def _extract_meeting_link(event: dict[str, Any]) -> str | None:
    """Extract video conferencing link from event.

    Checks for Google Meet links in conferenceData, then looks for
    common meeting URLs (Zoom, Teams) in location or description.

    Args:
        event: Google Calendar event dict.

    Returns:
        Meeting URL if found, None otherwise.
    """
    # Check Google Meet / conferenceData
    conference_data = event.get("conferenceData", {})
    entry_points = conference_data.get("entryPoints", [])
    for entry in entry_points:
        if entry.get("entryPointType") == "video":
            return entry.get("uri")

    # Check hangoutLink (older Google Meet format)
    if "hangoutLink" in event:
        return event["hangoutLink"]

    # Check location for meeting URLs
    location = event.get("location", "") or ""
    if "zoom.us" in location or "teams.microsoft.com" in location:
        # Extract URL from location (simple approach)
        for word in location.split():
            if "zoom.us" in word or "teams.microsoft.com" in word:
                return word.strip()

    return None


@router.post("/sync", response_model=SyncResponse)
async def trigger_sync(
    request: Request,
    background: bool = False,
    db: AsyncSession = Depends(get_db),
) -> SyncResponse:
    """Trigger calendar sync.

    Syncs calendar events from Google Calendar to the local database.
    Uses incremental sync tokens to efficiently fetch only changed events.

    Args:
        background: If True, queue as ARQ background task. If False, sync synchronously.
        db: Database session.

    Returns:
        Sync status with counts (if synchronous) or job ID (if background).

    Raises:
        HTTPException: If authentication is required.
    """
    if not is_authenticated():
        raise HTTPException(status_code=401, detail="Calendar not authenticated")

    if background:
        # Queue ARQ task
        arq_pool = request.app.state.arq_pool
        job = await arq_pool.enqueue_job("sync_calendar_task")
        logger.info("calendar_sync_queued", job_id=job.job_id)
        return SyncResponse(status="queued", job_id=job.job_id)
    else:
        from jarvis_server.calendar.sync import sync_calendar

        result = await sync_calendar(db)
        logger.info("calendar_sync_completed", **result)
        return SyncResponse(status="completed", **result)


@router.get("/events", response_model=list[StoredEventResponse])
async def list_events(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> list[StoredEventResponse]:
    """List synced calendar events from the local database.

    Returns events that have been synced from Google Calendar.
    Use /sync endpoint to sync events first.

    Args:
        start_date: Filter events starting after this date (inclusive).
        end_date: Filter events ending before this date (inclusive).
        limit: Maximum events to return (default 50, max 100).

    Returns:
        List of stored calendar events.
    """
    # Cap the limit
    limit = min(limit, 100)

    query = select(CalendarEvent).order_by(CalendarEvent.start_time)

    if start_date:
        query = query.where(CalendarEvent.start_time >= start_date)
    if end_date:
        query = query.where(CalendarEvent.end_time <= end_date)

    query = query.limit(limit)

    result = await db.execute(query)
    events = result.scalars().all()

    logger.info("calendar_events_listed", count=len(events))

    return [
        StoredEventResponse(
            id=e.id,
            summary=e.summary,
            start_time=e.start_time.isoformat(),
            end_time=e.end_time.isoformat(),
            location=e.location,
            meeting_link=e.meeting_link,
            attendees=json.loads(e.attendees_json) if e.attendees_json else [],
        )
        for e in events
    ]
