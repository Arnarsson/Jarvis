"""Meeting MCP tools for accessing meeting intelligence."""

from __future__ import annotations

import time
from typing import Annotated

import httpx
import structlog
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import Field

from jarvis_mcp.audit import log_mcp_call
from jarvis_mcp.client import get_client
from jarvis_mcp.server import mcp

logger = structlog.get_logger("jarvis_mcp.tools.meetings")


@mcp.tool()
async def get_meeting_brief(
    event_id: Annotated[
        str,
        Field(
            min_length=1,
            description="Calendar event ID to get brief for",
        ),
    ],
    regenerate: Annotated[
        bool,
        Field(
            default=False,
            description="Force regenerate brief even if cached",
        ),
    ] = False,
) -> str:
    """Get a pre-meeting brief for a calendar event.

    Generates a contextual briefing by searching your memory for relevant
    information about the meeting topic and attendees.

    Useful before meetings to get caught up on:
    - Previous discussions about this topic
    - Recent interactions with attendees
    - Open action items or follow-ups

    Examples:
    - "Give me a brief for my next meeting"
    - "What context do I have for the product review meeting?"
    """
    start_time = time.monotonic()
    input_params = {"event_id": event_id, "regenerate": regenerate}

    try:
        client = await get_client()

        response = await client.post(
            f"/api/meetings/brief/{event_id}",
            params={"force_regenerate": regenerate},
        )
        response.raise_for_status()
        data = response.json()

        result = f"# Pre-Meeting Brief: {data['event_summary']}\n\n{data['brief']}"

        if data.get("was_cached"):
            result += "\n\n*This brief was cached from a previous request.*"

        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="get_meeting_brief",
            input_params=input_params,
            result_summary="Brief generated",
            duration_ms=duration_ms,
            success=True,
        )
        return result

    except httpx.HTTPStatusError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="get_meeting_brief",
            input_params=input_params,
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=f"HTTP {e.response.status_code}",
        )
        if e.response.status_code == 404:
            raise ToolError(f"Calendar event not found: {event_id}")
        raise ToolError("Failed to generate meeting brief")

    except Exception as e:
        logger.exception("get_meeting_brief_failed", event_id=event_id)
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="get_meeting_brief",
            input_params=input_params,
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=str(e),
        )
        raise ToolError("Failed to generate meeting brief")


@mcp.tool()
async def get_meeting_summary(
    meeting_id: Annotated[
        str,
        Field(
            min_length=1,
            description="Meeting ID to get summary for",
        ),
    ],
) -> str:
    """Get summary and action items from a past meeting.

    Returns the AI-generated summary, action items with owners,
    key decisions, and follow-ups from a transcribed meeting.

    Examples:
    - "What happened in yesterday's standup?"
    - "What action items came out of the planning meeting?"
    - "Summarize my last meeting"
    """
    start_time = time.monotonic()
    input_params = {"meeting_id": meeting_id}

    try:
        client = await get_client()

        response = await client.get(f"/api/meetings/summary/{meeting_id}")
        response.raise_for_status()
        data = response.json()

        lines = ["# Meeting Summary\n"]

        if data.get("calendar_event_summary"):
            lines.append(f"**Meeting:** {data['calendar_event_summary']}\n")

        lines.append(f"## Summary\n{data['summary']}\n")

        action_items = data.get("action_items", [])
        if action_items:
            lines.append("## Action Items")
            for item in action_items:
                owner = item.get("owner") or "Unassigned"
                priority = item.get("priority", "medium")
                due = item.get("due_date")
                line = f"- [{priority.upper()}] {item['task']} (Owner: {owner})"
                if due:
                    line += f" - Due: {due}"
                lines.append(line)
            lines.append("")

        if data.get("transcript_available"):
            lines.append("*Full transcript available*")

        result = "\n".join(lines)

        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="get_meeting_summary",
            input_params=input_params,
            result_summary="Summary retrieved",
            duration_ms=duration_ms,
            success=True,
        )
        return result

    except httpx.HTTPStatusError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="get_meeting_summary",
            input_params=input_params,
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=f"HTTP {e.response.status_code}",
        )
        if e.response.status_code == 404:
            raise ToolError(f"Meeting or summary not found: {meeting_id}")
        raise ToolError("Failed to get meeting summary")

    except Exception as e:
        logger.exception("get_meeting_summary_failed", meeting_id=meeting_id)
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="get_meeting_summary",
            input_params=input_params,
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=str(e),
        )
        raise ToolError("Failed to get meeting summary")


@mcp.tool()
async def get_current_meeting() -> str:
    """Check if there's a currently active meeting.

    Returns information about any ongoing meeting detected by the system,
    including the platform (Zoom, Google Meet, etc.) and start time.

    Useful to check:
    - "Am I in a meeting right now?"
    - "What meeting am I in?"
    """
    start_time = time.monotonic()
    input_params: dict = {}

    try:
        client = await get_client()

        response = await client.get("/api/meetings/current")
        response.raise_for_status()
        data = response.json()

        if not data:
            result = "No active meeting detected."
        else:
            platform = data.get("platform", "Unknown")
            detected_at = data.get("detected_at", "Unknown")
            has_summary = data.get("has_summary", False)

            result = f"Currently in a {platform} meeting.\nStarted: {detected_at}"
            if has_summary:
                result += "\n*Summary available after meeting ends.*"

        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="get_current_meeting",
            input_params=input_params,
            result_summary="Status checked",
            duration_ms=duration_ms,
            success=True,
        )
        return result

    except httpx.HTTPStatusError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="get_current_meeting",
            input_params=input_params,
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=f"HTTP {e.response.status_code}",
        )
        raise ToolError("Failed to check meeting status")

    except Exception as e:
        logger.exception("get_current_meeting_failed")
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="get_current_meeting",
            input_params=input_params,
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=str(e),
        )
        raise ToolError("Failed to check meeting status")
