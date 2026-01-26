"""Context recovery tool for catching up on topics.

This module implements the catch_me_up MCP tool which helps users
recover context on any project or topic by summarizing recent activity
using AI-powered summarization.
"""

from __future__ import annotations

import time
from typing import Annotated, Literal

import httpx
import structlog
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import Field

from jarvis_mcp.audit import log_mcp_call
from jarvis_mcp.client import get_client
from jarvis_mcp.server import mcp
from jarvis_mcp.validators import validate_topic

logger = structlog.get_logger(__name__)


@mcp.tool()
async def catch_me_up(
    topic: Annotated[
        str,
        Field(
            min_length=1,
            max_length=500,
            description="Project name, topic, or area to get caught up on",
        ),
    ],
    days: Annotated[
        int,
        Field(
            default=7,
            ge=1,
            le=90,
            description="How many days back to look",
        ),
    ] = 7,
    style: Annotated[
        Literal["summary", "detailed"],
        Field(
            default="detailed",
            description="Summary style: 'summary' for brief overview, 'detailed' for comprehensive briefing",
        ),
    ] = "detailed",
) -> str:
    """Get an AI-generated context summary for a topic or project.

    Searches across all memory sources (screen captures, emails, chats,
    calendar events) and uses Claude to synthesize a comprehensive briefing
    covering timeline, key points, people involved, and next steps.

    Examples:
    - "project alpha" - get full briefing on project activity
    - "API redesign" - catch up on API discussions and decisions
    - "team standup" - review recent standup notes and action items
    """
    start_time = time.monotonic()

    try:
        # Validate and sanitize input
        sanitized_topic = validate_topic(topic)

        # Call the catchup API which uses Claude for summarization
        client = await get_client()
        response = await client.post(
            "/api/catchup/",
            json={
                "topic": sanitized_topic,
                "days_back": days,
                "style": style,
            },
            timeout=60.0,  # Allow time for LLM summarization
        )
        response.raise_for_status()
        data = response.json()

        summary = data.get("summary", "No summary generated.")
        sources = data.get("sources_searched", {})
        total_items = sum(sources.values())

        # Build result with metadata
        lines = [
            f"# Catch-up: {topic}",
            f"*Last {days} days | {total_items} items from {len(sources)} sources*\n",
            summary,
        ]

        if sources:
            lines.append("\n---")
            lines.append("**Sources:** " + ", ".join(
                f"{k}({v})" for k, v in sources.items()
            ))

        result_text = "\n".join(lines)

        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="catch_me_up",
            input_params={"topic": topic, "days": days, "style": style},
            result_summary=f"Generated {style} summary from {total_items} items",
            duration_ms=duration_ms,
            success=True,
        )

        return result_text

    except httpx.HTTPStatusError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="catch_me_up",
            input_params={"topic": topic, "days": days, "style": style},
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=str(e),
        )
        raise ToolError("Context recovery temporarily unavailable")

    except httpx.TimeoutException:
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="catch_me_up",
            input_params={"topic": topic, "days": days, "style": style},
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error="Timeout waiting for summary generation",
        )
        raise ToolError("Summary generation timed out - try a shorter timeframe")

    except Exception as e:
        logger.exception("catch_me_up_failed")
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="catch_me_up",
            input_params={"topic": topic, "days": days, "style": style},
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=str(e),
        )
        raise ToolError("Context recovery failed")


@mcp.tool()
async def morning_briefing() -> str:
    """Get your morning briefing with today's schedule and relevant context.

    Provides a comprehensive overview of your day including:
    - Today's calendar events and meetings
    - Key topics from your schedule
    - Relevant context from recent activity

    Use this at the start of your day to get up to speed quickly.
    """
    start_time = time.monotonic()

    try:
        client = await get_client()
        response = await client.get(
            "/api/catchup/morning",
            timeout=90.0,  # Allow time for LLM summarization
        )
        response.raise_for_status()
        data = response.json()

        date = data.get("date", "today")
        meetings = data.get("meetings_today", [])
        briefing = data.get("briefing", "No briefing available.")

        # Build formatted output
        lines = [
            f"# Morning Briefing - {date}",
            "",
        ]

        if meetings:
            lines.append(f"**{len(meetings)} meeting(s) today:**")
            for m in meetings:
                attendees = ", ".join(m.get("attendees", [])[:3])
                if attendees:
                    lines.append(f"- {m['time']}: {m['title']} ({attendees})")
                else:
                    lines.append(f"- {m['time']}: {m['title']}")
            lines.append("")

        lines.append(briefing)

        result_text = "\n".join(lines)

        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="morning_briefing",
            input_params={},
            result_summary=f"Generated briefing with {len(meetings)} meetings",
            duration_ms=duration_ms,
            success=True,
        )

        return result_text

    except httpx.HTTPStatusError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="morning_briefing",
            input_params={},
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=str(e),
        )
        raise ToolError("Morning briefing temporarily unavailable")

    except httpx.TimeoutException:
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="morning_briefing",
            input_params={},
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error="Timeout waiting for briefing generation",
        )
        raise ToolError("Morning briefing generation timed out")

    except Exception as e:
        logger.exception("morning_briefing_failed")
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="morning_briefing",
            input_params={},
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=str(e),
        )
        raise ToolError("Morning briefing failed")
