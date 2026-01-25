"""Email tools for accessing Gmail context via MCP."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Annotated, Optional

import structlog
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import Field

from jarvis_mcp.audit import log_mcp_call
from jarvis_mcp.client import get_client
from jarvis_mcp.server import mcp

logger = structlog.get_logger("jarvis_mcp.tools.email")


@mcp.tool()
async def search_emails(
    query: Annotated[
        str,
        Field(
            min_length=1,
            max_length=500,
            description="Search query for finding emails (topic, person, or keywords)",
        ),
    ],
    limit: Annotated[
        int,
        Field(
            default=10,
            ge=1,
            le=30,
            description="Maximum number of emails to return",
        ),
    ] = 10,
    days_back: Annotated[
        int,
        Field(
            default=30,
            ge=1,
            le=365,
            description="How many days back to search",
        ),
    ] = 30,
) -> str:
    """Search emails in Jarvis memory.

    Finds relevant emails using semantic search across your synced Gmail.
    Useful for finding conversations about specific topics or with specific people.

    Examples:
    - "emails from John about the project proposal"
    - "budget discussion with finance team"
    - "meeting follow-up from last week"
    """
    start_time = time.monotonic()
    input_params = {"query": query, "limit": limit, "days_back": days_back}

    try:
        client = await get_client()

        start_date = (datetime.now() - timedelta(days=days_back)).isoformat()

        response = await client.post(
            "/api/search/",
            json={
                "query": query,
                "limit": limit,
                "sources": ["email"],
                "start_date": start_date,
            },
        )
        response.raise_for_status()

        data = response.json()
        results = data.get("results", [])
        total = data.get("total", len(results))

        if not results:
            result_text = f"No matching emails found in the last {days_back} days."
        else:
            lines = [f"Found {total} relevant email(s):\n"]
            for i, result in enumerate(results, 1):
                timestamp = result.get("timestamp", "")
                date_str = timestamp[:10] if len(timestamp) >= 10 else "Unknown"
                preview = result.get("text_preview", "")

                lines.append(f"{i}. {preview[:150]}...")
                lines.append(f"   Date: {date_str}")
            result_text = "\n\n".join(lines)

        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="search_emails",
            input_params=input_params,
            result_summary=f"Found {total} emails",
            duration_ms=duration_ms,
            success=True,
        )

        return result_text

    except Exception as e:
        logger.exception("search_emails_failed")
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="search_emails",
            input_params=input_params,
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=str(e),
        )
        raise ToolError("Email search failed")


@mcp.tool()
async def get_recent_emails(
    from_address: Annotated[
        Optional[str],
        Field(
            default=None,
            description="Filter by sender email address (partial match)",
        ),
    ] = None,
    limit: Annotated[
        int,
        Field(
            default=10,
            ge=1,
            le=50,
            description="Maximum number of emails to return",
        ),
    ] = 10,
) -> str:
    """Get recent emails from your inbox.

    Lists the most recent synced emails, optionally filtered by sender.
    Useful for checking what emails came in recently.
    """
    start_time = time.monotonic()
    input_params = {"from_address": from_address, "limit": limit}

    try:
        client = await get_client()

        params = {"limit": limit}
        if from_address:
            params["from_address"] = from_address

        response = await client.get("/api/email/messages", params=params)
        response.raise_for_status()

        emails = response.json()

        if not emails:
            filter_msg = f" from {from_address}" if from_address else ""
            result_text = f"No recent emails found{filter_msg}."
        else:
            lines = [f"Recent emails ({len(emails)}):\n"]
            for i, email in enumerate(emails, 1):
                date_sent = email.get("date_sent", "")
                date_str = date_sent[:10] if date_sent else "Unknown"
                from_name = email.get("from_name") or email.get("from_address", "Unknown")
                subject = email.get("subject", "No subject")
                snippet = email.get("snippet", "")[:100]

                lines.append(
                    f"{i}. **{subject}**\n"
                    f"   From: {from_name} | {date_str}\n"
                    f"   {snippet}..."
                )
            result_text = "\n\n".join(lines)

        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="get_recent_emails",
            input_params=input_params,
            result_summary=f"Found {len(emails)} emails",
            duration_ms=duration_ms,
            success=True,
        )

        return result_text

    except Exception as e:
        logger.exception("get_recent_emails_failed")
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="get_recent_emails",
            input_params=input_params,
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=str(e),
        )
        raise ToolError("Failed to get recent emails")


@mcp.tool()
async def get_email_status() -> str:
    """Check Gmail connection status.

    Returns whether Gmail is authenticated and syncing.
    """
    start_time = time.monotonic()

    try:
        client = await get_client()
        response = await client.get("/api/email/auth/status")
        response.raise_for_status()
        status = response.json()

        if status.get("authenticated"):
            result = "Gmail is connected and syncing."
        elif status.get("needs_credentials"):
            result = (
                "Gmail is not set up. "
                "Please place your Google OAuth credentials.json file in the data/email directory."
            )
        else:
            result = "Gmail needs authentication. Run the OAuth flow to connect."

        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="get_email_status",
            input_params={},
            result_summary=result[:50],
            duration_ms=duration_ms,
            success=True,
        )

        return result

    except Exception as e:
        logger.exception("get_email_status_failed")
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="get_email_status",
            input_params={},
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=str(e),
        )
        raise ToolError("Failed to check email status")
