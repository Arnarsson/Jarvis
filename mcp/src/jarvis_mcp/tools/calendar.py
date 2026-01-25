"""Calendar MCP tools for accessing calendar events."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Annotated

import httpx
import structlog
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import Field

from jarvis_mcp.audit import log_mcp_call
from jarvis_mcp.client import get_client
from jarvis_mcp.server import mcp

logger = structlog.get_logger("jarvis_mcp.tools.calendar")


@mcp.tool()
async def get_upcoming_events(
    hours: Annotated[
        int,
        Field(
            default=24,
            ge=1,
            le=168,  # Max 1 week
            description="Number of hours to look ahead (default 24)",
        ),
    ] = 24,
    limit: Annotated[
        int,
        Field(
            default=10,
            ge=1,
            le=50,
            description="Maximum number of events to return",
        ),
    ] = 10,
) -> str:
    """Get upcoming calendar events.

    Shows your scheduled meetings and events for the specified time period.
    Useful for checking your schedule and preparing for upcoming meetings.

    Examples:
    - "What meetings do I have today?"
    - "What's on my calendar this week?"
    - "Do I have any meetings in the next 2 hours?"
    """
    start_time = time.monotonic()
    input_params = {"hours": hours, "limit": limit}

    try:
        client = await get_client()

        # Calculate date range
        now = datetime.now()
        end = now + timedelta(hours=hours)

        response = await client.get(
            "/api/calendar/events",
            params={
                "start_date": now.isoformat(),
                "end_date": end.isoformat(),
                "limit": limit,
            },
        )
        response.raise_for_status()
        events = response.json()

        if not events:
            result = f"No events scheduled in the next {hours} hours."
        else:
            lines = [f"Found {len(events)} upcoming events:\n"]
            for i, event in enumerate(events, 1):
                start = datetime.fromisoformat(event["start_time"])
                start_str = start.strftime("%a %b %d %I:%M %p")
                summary = event.get("summary", "Untitled")
                location = event.get("location")

                line = f"{i}. **{summary}**\n   {start_str}"
                if location:
                    line += f"\n   Location: {location}"
                if event.get("meeting_link"):
                    line += f"\n   Link: {event['meeting_link']}"

                attendees = event.get("attendees", [])
                if attendees:
                    names = [
                        a.get("displayName") or a.get("email", "?").split("@")[0]
                        for a in attendees[:5]
                    ]
                    line += f"\n   With: {', '.join(names)}"
                    if len(attendees) > 5:
                        line += f" (+{len(attendees) - 5} more)"

                lines.append(line)

            result = "\n\n".join(lines)

        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="get_upcoming_events",
            input_params=input_params,
            result_summary=f"Found {len(events) if events else 0} events",
            duration_ms=duration_ms,
            success=True,
        )
        return result

    except httpx.HTTPStatusError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="get_upcoming_events",
            input_params=input_params,
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=f"HTTP {e.response.status_code}",
        )
        raise ToolError("Failed to fetch calendar events")

    except Exception as e:
        logger.exception("get_upcoming_events_failed")
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="get_upcoming_events",
            input_params=input_params,
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=str(e),
        )
        raise ToolError("Failed to fetch calendar events")


@mcp.tool()
async def get_calendar_status() -> str:
    """Check Google Calendar connection status.

    Returns whether Google Calendar is authenticated and syncing.
    If not authenticated, provides guidance on how to set up.
    """
    start_time = time.monotonic()
    input_params: dict = {}

    try:
        client = await get_client()
        response = await client.get("/api/calendar/auth/status")
        response.raise_for_status()
        status = response.json()

        if status.get("authenticated"):
            result = "Google Calendar is connected and syncing."
        elif status.get("needs_credentials"):
            result = (
                "Google Calendar is not set up. "
                "Please place your Google OAuth credentials.json file in the data directory "
                "and restart the server to begin authentication."
            )
        else:
            result = (
                "Google Calendar needs authentication. "
                "Run the OAuth flow to connect your calendar."
            )

        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="get_calendar_status",
            input_params=input_params,
            result_summary="Status retrieved",
            duration_ms=duration_ms,
            success=True,
        )
        return result

    except httpx.HTTPStatusError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="get_calendar_status",
            input_params=input_params,
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=f"HTTP {e.response.status_code}",
        )
        raise ToolError("Failed to check calendar status")

    except Exception as e:
        logger.exception("get_calendar_status_failed")
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="get_calendar_status",
            input_params=input_params,
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=str(e),
        )
        raise ToolError("Failed to check calendar status")
