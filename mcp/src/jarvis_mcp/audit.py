"""Audit logging infrastructure for MCP tool invocations.

This module provides structured logging for all MCP tool calls,
enabling compliance tracking, debugging, and security monitoring.

All tool invocations should be logged through log_mcp_call() which
captures timing, parameters (sanitized), results, and errors.
"""

from __future__ import annotations

from typing import Any

import structlog

# Get dedicated logger for audit trail
logger = structlog.get_logger("jarvis_mcp.audit")

# Truncation limits to prevent log bloat
MAX_STRING_LENGTH = 200
TRUNCATED_PREFIX_LENGTH = 100
MAX_RESULT_LENGTH = 200
MAX_ERROR_LENGTH = 500
TRUNCATE_SUFFIX = "...[truncated]"


def _truncate_string(value: str, max_length: int = MAX_STRING_LENGTH) -> str:
    """Truncate a string if it exceeds max length.

    Args:
        value: String to potentially truncate
        max_length: Maximum allowed length

    Returns:
        Original string if within limit, or truncated with suffix
    """
    if len(value) <= max_length:
        return value
    return value[:TRUNCATED_PREFIX_LENGTH] + TRUNCATE_SUFFIX


def _sanitize_for_log(params: dict[str, Any]) -> dict[str, Any]:
    """Sanitize parameters dictionary for logging.

    Truncates string values that exceed MAX_STRING_LENGTH to prevent
    large queries from bloating log files.

    Args:
        params: Dictionary of tool parameters

    Returns:
        Sanitized copy with long strings truncated
    """
    sanitized: dict[str, Any] = {}

    for key, value in params.items():
        if isinstance(value, str):
            sanitized[key] = _truncate_string(value)
        elif isinstance(value, dict):
            # Recursively sanitize nested dicts
            sanitized[key] = _sanitize_for_log(value)
        elif isinstance(value, list):
            # Sanitize list items
            sanitized[key] = [
                _truncate_string(item) if isinstance(item, str) else item
                for item in value
            ]
        else:
            # Preserve non-string values as-is (int, float, bool, None)
            sanitized[key] = value

    return sanitized


def log_mcp_call(
    tool_name: str,
    input_params: dict[str, Any],
    result_summary: str,
    duration_ms: float,
    success: bool,
    error: str | None = None,
) -> None:
    """Log an MCP tool invocation with structured data.

    This function should be called after every MCP tool execution,
    whether successful or failed. It provides an audit trail of all
    tool usage for compliance and debugging.

    Args:
        tool_name: Name of the MCP tool that was invoked
        input_params: Dictionary of parameters passed to the tool
        result_summary: Brief description of the result
        duration_ms: Execution time in milliseconds
        success: Whether the tool completed successfully
        error: Error message if the tool failed (optional)

    Example:
        >>> log_mcp_call(
        ...     tool_name="search_memory",
        ...     input_params={"query": "meetings about API design", "limit": 10},
        ...     result_summary="Found 5 relevant captures",
        ...     duration_ms=123.45,
        ...     success=True,
        ... )

        >>> log_mcp_call(
        ...     tool_name="search_memory",
        ...     input_params={"query": "test"},
        ...     result_summary="",
        ...     duration_ms=50.0,
        ...     success=False,
        ...     error="Server connection timeout",
        ... )
    """
    # Sanitize parameters to prevent log bloat
    sanitized_params = _sanitize_for_log(input_params)

    # Truncate result summary
    truncated_result = _truncate_string(result_summary, MAX_RESULT_LENGTH)

    # Round duration to 2 decimal places
    rounded_duration = round(duration_ms, 2)

    # Build log fields
    log_fields = {
        "tool": tool_name,
        "params": sanitized_params,
        "result_summary": truncated_result,
        "duration_ms": rounded_duration,
        "success": success,
    }

    if success:
        logger.info("mcp_tool_invoked", **log_fields)
    else:
        # Truncate error message if present
        if error:
            log_fields["error"] = _truncate_string(error, MAX_ERROR_LENGTH)
        logger.error("mcp_tool_failed", **log_fields)
