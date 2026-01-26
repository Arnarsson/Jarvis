"""Workflow automation MCP tools.

Provides Claude Code with tools to view, approve, and trigger
workflow automations that Jarvis has learned from user patterns.
"""

from __future__ import annotations

import time
from typing import Annotated, Optional

import httpx
import structlog
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import Field

from jarvis_mcp.audit import log_mcp_call
from jarvis_mcp.client import get_client
from jarvis_mcp.server import mcp

logger = structlog.get_logger(__name__)


@mcp.tool()
async def jarvis_list_suggestions() -> str:
    """List pending automation suggestions that Jarvis has detected.

    Shows patterns Jarvis has observed frequently enough to suggest
    as automations. Review and approve or reject each suggestion.

    Returns a formatted list of suggestions with their confidence scores.
    """
    start_time = time.monotonic()

    try:
        client = await get_client()
        response = await client.get("/api/workflow/suggestions")
        response.raise_for_status()
        data = response.json()

        suggestions = data.get("suggestions", [])
        total = data.get("total", 0)

        if total == 0:
            result_text = "No pending suggestions. Jarvis is still learning your patterns."
        else:
            lines = [f"# {total} Pending Suggestion(s)\n"]
            for s in suggestions:
                confidence = round(s.get("confidence", 0) * 100)
                lines.append(f"## {s['name']}")
                lines.append(f"- **ID:** `{s['id']}`")
                lines.append(f"- **Type:** {s.get('pattern_type', 'unknown')}")
                lines.append(f"- **Description:** {s.get('description', 'N/A')}")
                lines.append(f"- **Trigger:** {s.get('trigger_description', 'N/A')}")
                lines.append(f"- **Action:** {s.get('action_description', 'N/A')}")
                lines.append(f"- **Confidence:** {confidence}%")
                lines.append("")
            lines.append("Use `jarvis_approve_automation` or `jarvis_reject_automation` with the pattern ID.")
            result_text = "\n".join(lines)

        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="jarvis_list_suggestions",
            input_params={},
            result_summary=f"Found {total} suggestions",
            duration_ms=duration_ms,
            success=True,
        )
        return result_text

    except httpx.HTTPStatusError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="jarvis_list_suggestions",
            input_params={},
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=str(e),
        )
        raise ToolError("Failed to fetch suggestions")

    except Exception as e:
        logger.exception("jarvis_list_suggestions_failed")
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="jarvis_list_suggestions",
            input_params={},
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=str(e),
        )
        raise ToolError("Failed to list suggestions")


@mcp.tool()
async def jarvis_approve_automation(
    pattern_id: Annotated[
        str,
        Field(
            min_length=1,
            description="The pattern ID to approve (from jarvis_list_suggestions)",
        ),
    ],
) -> str:
    """Approve a suggested automation pattern.

    Promotes the pattern from 'observe' to 'suggest' tier, meaning
    Jarvis will start recommending this automation when the pattern
    is detected (but won't auto-execute without approval).

    Use jarvis_list_suggestions first to see available suggestions.
    """
    start_time = time.monotonic()

    try:
        client = await get_client()
        response = await client.post(f"/api/workflow/suggestions/{pattern_id}/approve")
        response.raise_for_status()
        data = response.json()

        result_text = (
            f"Approved pattern `{pattern_id}`.\n"
            f"New tier: **{data.get('new_tier', 'suggest')}**\n\n"
            f"Jarvis will now suggest this automation when the pattern is detected."
        )

        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="jarvis_approve_automation",
            input_params={"pattern_id": pattern_id},
            result_summary=f"Approved {pattern_id}",
            duration_ms=duration_ms,
            success=True,
        )
        return result_text

    except httpx.HTTPStatusError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="jarvis_approve_automation",
            input_params={"pattern_id": pattern_id},
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=str(e),
        )
        if e.response.status_code == 404:
            raise ToolError(f"Pattern {pattern_id} not found")
        raise ToolError("Failed to approve automation")

    except Exception as e:
        logger.exception("jarvis_approve_automation_failed")
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="jarvis_approve_automation",
            input_params={"pattern_id": pattern_id},
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=str(e),
        )
        raise ToolError("Failed to approve automation")


@mcp.tool()
async def jarvis_list_automations(
    include_suspended: Annotated[
        bool,
        Field(
            default=False,
            description="Include suspended automations in the list",
        ),
    ] = False,
) -> str:
    """List active workflow automations.

    Shows all patterns that are currently active (suggest or auto tier).
    Includes accuracy stats and execution counts for each pattern.
    """
    start_time = time.monotonic()

    try:
        client = await get_client()
        active_only = "true" if not include_suspended else "false"
        response = await client.get(f"/api/workflow/patterns?active_only={active_only}")
        response.raise_for_status()
        data = response.json()

        patterns = data.get("patterns", [])

        if not patterns:
            result_text = "No active automations. Approve suggestions to create automations."
        else:
            lines = [f"# {len(patterns)} Automation(s)\n"]
            for p in patterns:
                status = "Active" if p.get("is_active") else "Suspended"
                accuracy = round(p.get("accuracy", 0) * 100)
                lines.append(f"## {p['name']} [{status}]")
                lines.append(f"- **ID:** `{p['id']}`")
                lines.append(f"- **Tier:** {p.get('trust_tier', 'unknown')}")
                lines.append(f"- **Type:** {p.get('pattern_type', 'unknown')}")
                if p.get("description"):
                    lines.append(f"- **Description:** {p['description']}")
                lines.append(f"- **Frequency:** seen {p.get('frequency_count', 0)} times")
                lines.append(f"- **Accuracy:** {accuracy}%")
                lines.append(f"- **Executions:** {p.get('total_executions', 0)}")
                lines.append("")
            result_text = "\n".join(lines)

        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="jarvis_list_automations",
            input_params={"include_suspended": include_suspended},
            result_summary=f"Found {len(patterns)} patterns",
            duration_ms=duration_ms,
            success=True,
        )
        return result_text

    except httpx.HTTPStatusError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="jarvis_list_automations",
            input_params={"include_suspended": include_suspended},
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=str(e),
        )
        raise ToolError("Failed to list automations")

    except Exception as e:
        logger.exception("jarvis_list_automations_failed")
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="jarvis_list_automations",
            input_params={"include_suspended": include_suspended},
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=str(e),
        )
        raise ToolError("Failed to list automations")


@mcp.tool()
async def jarvis_trigger_automation(
    pattern_id: Annotated[
        str,
        Field(
            min_length=1,
            description="The pattern ID to trigger (from jarvis_list_automations)",
        ),
    ],
) -> str:
    """Manually trigger a workflow automation.

    Executes the actions defined in the pattern. Only works for
    patterns in 'suggest' or 'auto' tier. Returns execution results
    including any errors.

    Use jarvis_list_automations first to see available automations.
    """
    start_time = time.monotonic()

    try:
        client = await get_client()
        response = await client.post(
            f"/api/workflow/execute/{pattern_id}",
            json={"user_approved": True},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

        status = data.get("status", "unknown")
        exec_id = data.get("execution_id", "N/A")
        completed = data.get("actions_completed", 0)
        failed = data.get("actions_failed", 0)

        lines = [
            f"# Execution Result: {status.upper()}\n",
            f"- **Execution ID:** `{exec_id}`",
            f"- **Actions completed:** {completed}",
            f"- **Actions failed:** {failed}",
        ]

        if data.get("error"):
            lines.append(f"- **Error:** {data['error']}")

        result_text = "\n".join(lines)

        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="jarvis_trigger_automation",
            input_params={"pattern_id": pattern_id},
            result_summary=f"Execution {status}: {completed} completed, {failed} failed",
            duration_ms=duration_ms,
            success=status == "completed",
        )
        return result_text

    except httpx.HTTPStatusError as e:
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="jarvis_trigger_automation",
            input_params={"pattern_id": pattern_id},
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=str(e),
        )
        if e.response.status_code == 400:
            detail = e.response.json().get("detail", "Execution failed")
            raise ToolError(f"Cannot execute: {detail}")
        if e.response.status_code == 404:
            raise ToolError(f"Pattern {pattern_id} not found")
        raise ToolError("Failed to trigger automation")

    except httpx.TimeoutException:
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="jarvis_trigger_automation",
            input_params={"pattern_id": pattern_id},
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error="Execution timed out",
        )
        raise ToolError("Automation execution timed out")

    except Exception as e:
        logger.exception("jarvis_trigger_automation_failed")
        duration_ms = (time.monotonic() - start_time) * 1000
        log_mcp_call(
            tool_name="jarvis_trigger_automation",
            input_params={"pattern_id": pattern_id},
            result_summary="",
            duration_ms=duration_ms,
            success=False,
            error=str(e),
        )
        raise ToolError("Failed to trigger automation")
