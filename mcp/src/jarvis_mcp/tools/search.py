"""Search memory tool for querying Jarvis captures and documents."""

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
from jarvis_mcp.validators import validate_search_query

logger = structlog.get_logger("jarvis_mcp.tools.search")


@mcp.tool()
async def search_memory(
    query: Annotated[
        str,
        Field(
            min_length=1,
            max_length=1000,
            description="Natural language search query for finding information in your memory",
        ),
    ],
    limit: Annotated[
        int,
        Field(
            default=10,
            ge=1,
            le=50,
            description="Maximum number of results to return",
        ),
    ] = 10,
    sources: Annotated[
        list[str] | None,
        Field(
            default=None,
            description="Filter by source: screen, chatgpt, claude, grok",
        ),
    ] = None,
) -> str:
    """Search all Jarvis memory sources using semantic and keyword matching.

    Finds relevant screen captures, chat conversations, and documents
    across all imported sources. Results are ranked by relevance using
    hybrid search (semantic understanding + keyword matching).

    Examples:
    - "meetings about project alpha last week"
    - "code review feedback from yesterday"
    - "discussion about API design in Claude"
    """
    start_time = time.monotonic()
    input_params = {"query": query, "limit": limit, "sources": sources}

    try:
        # Validate and sanitize the query
        sanitized_query = validate_search_query(query)

        # Get HTTP client and make request
        client = await get_client()
        response = await client.post(
            "/api/search/",
            json={
                "query": sanitized_query,
                "limit": limit,
                "sources": sources,
            },
        )
        response.raise_for_status()

        # Parse response
        data = response.json()
        results = data.get("results", [])
        total = data.get("total", len(results))

        # Format results as readable text
        if not results:
            result_text = "No matching memories found."
        else:
            lines = [f"Found {total} relevant memories:\n"]
            for i, result in enumerate(results, 1):
                source = result.get("source", "unknown")
                timestamp = result.get("timestamp", "")
                # Format timestamp to be more readable
                if timestamp:
                    # Take just the date part if it's an ISO timestamp
                    date_part = timestamp[:10] if len(timestamp) >= 10 else timestamp
                else:
                    date_part = "unknown date"
                text_preview = result.get("text_preview", "")
                lines.append(f"{i}. [{source}] {date_part}\n   {text_preview}")
            result_text = "\n".join(lines)

        # Calculate duration and log success
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="search_memory",
            input_params=input_params,
            result_summary=f"Found {total} results",
            duration_ms=duration_ms,
            success=True,
        )

        return result_text

    except httpx.HTTPStatusError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="search_memory",
            input_params=input_params,
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=f"HTTP {e.response.status_code}",
        )
        raise ToolError("Memory search temporarily unavailable")

    except ValueError as e:
        # Re-raise validation errors with clear message
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="search_memory",
            input_params=input_params,
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=str(e),
        )
        raise ToolError(str(e))

    except Exception as e:
        logger.exception("search_memory_failed")
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="search_memory",
            input_params=input_params,
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=str(e),
        )
        raise ToolError("Search failed unexpectedly")
