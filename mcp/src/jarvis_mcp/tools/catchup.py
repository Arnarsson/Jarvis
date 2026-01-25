"""Context recovery tool for catching up on topics.

This module implements the catch_me_up MCP tool which helps users
recover context on any project or topic by summarizing recent activity.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Annotated

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
            le=30,
            description="How many days back to look",
        ),
    ] = 7,
) -> str:
    """Get a context summary for a topic or project.

    Reviews recent activity across all memory sources related to the
    specified topic, then provides a chronological summary to help you
    get back up to speed quickly.

    Examples:
    - "project alpha" - summarize recent project activity
    - "API redesign" - catch up on API discussions
    - "team standup" - review recent standup notes
    """
    start_time = time.monotonic()

    try:
        # Validate and sanitize input
        sanitized_topic = validate_topic(topic)

        # Calculate date range
        end_date = datetime.now(tz=timezone.utc)
        start_date = end_date - timedelta(days=days)

        # Query the search API with date filter
        client = await get_client()
        response = await client.post(
            "/api/search/",
            json={
                "query": sanitized_topic,
                "limit": 20,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
        )
        response.raise_for_status()
        data = response.json()

        results = data.get("results", [])

        # Format results grouped by date
        if not results:
            result_text = (
                f"No activity found for '{topic}' in the last {days} days."
            )
            duration_ms = (time.monotonic() - start_time) * 1000
            log_mcp_call(
                tool_name="catch_me_up",
                input_params={"topic": topic, "days": days},
                result_summary="No results found",
                duration_ms=duration_ms,
                success=True,
            )
            return result_text

        # Group results by date
        by_date: dict[str, list[dict]] = {}
        for r in results:
            date_key = r.get("timestamp", "")[:10]
            if date_key:
                by_date.setdefault(date_key, []).append(r)

        # Build formatted output
        lines = [
            f"Context recovery for '{topic}' (last {days} days):\n",
            f"Found {len(results)} relevant items across {len(by_date)} days.\n",
        ]

        # Sort dates descending and limit to 5
        sorted_dates = sorted(by_date.keys(), reverse=True)[:5]

        for date in sorted_dates:
            lines.append(f"\n**{date}**:")
            # Limit to 3 items per date
            for item in by_date[date][:3]:
                source = item.get("source", "unknown")
                text = item.get("text", "")[:100]
                lines.append(f"  - [{source}] {text}")

        result_text = "\n".join(lines)

        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="catch_me_up",
            input_params={"topic": topic, "days": days},
            result_summary=f"Found {len(results)} items across {len(by_date)} days",
            duration_ms=duration_ms,
            success=True,
        )

        return result_text

    except httpx.HTTPStatusError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="catch_me_up",
            input_params={"topic": topic, "days": days},
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=str(e),
        )
        raise ToolError("Context recovery temporarily unavailable")

    except Exception as e:
        logger.exception("catch_me_up_failed")
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="catch_me_up",
            input_params={"topic": topic, "days": days},
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=str(e),
        )
        raise ToolError("Context recovery failed")
