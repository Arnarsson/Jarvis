"""Calendar API endpoints for OAuth and event access."""

from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from jarvis_server.calendar.oauth import (
    CalendarAuthRequired,
    CredentialsNotFound,
    credentials_exist,
    get_calendar_service,
    is_authenticated,
    start_oauth_flow,
)

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
