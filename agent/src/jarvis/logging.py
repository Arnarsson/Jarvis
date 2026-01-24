"""Structured JSON logging for Jarvis agent.

Provides audit-friendly logging with contextual fields for capture events,
upload operations, and state changes. All sensitive data is excluded from logs.

Usage:
    from jarvis.logging import setup_logging, get_logger

    setup_logging("INFO")
    log = get_logger("jarvis.capture")
    log.info("capture_taken", extra={"monitor_index": 0, "file_size": 50000})
"""

from __future__ import annotations

import logging
import sys
from functools import lru_cache
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING

from pythonjsonlogger import jsonlogger

if TYPE_CHECKING:
    pass

# Agent version - used in log context
AGENT_VERSION = "0.1.0"

# Default agent identifier (can be overridden)
_agent_id: str | None = None


class JarvisJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter that adds agent context to all log records."""

    def add_fields(
        self,
        log_record: dict,
        record: logging.LogRecord,
        message_dict: dict,
    ) -> None:
        """Add standard fields to every log record."""
        super().add_fields(log_record, record, message_dict)

        # ISO 8601 timestamp
        log_record["timestamp"] = self.formatTime(record)

        # Standard fields
        log_record["level"] = record.levelname
        log_record["logger"] = record.name

        # Agent context
        log_record["agent_version"] = AGENT_VERSION
        if _agent_id:
            log_record["agent_id"] = _agent_id

        # Move message to consistent position
        if "message" not in log_record and record.getMessage():
            log_record["message"] = record.getMessage()

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        """Format time as ISO 8601."""
        from datetime import datetime, timezone

        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        return dt.isoformat()


def setup_logging(
    level: str = "INFO",
    log_file: Path | None = None,
    agent_id: str | None = None,
    max_bytes: int = 10_000_000,  # 10MB
    backup_count: int = 5,
) -> None:
    """Configure root logger with JSON formatting.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path for rotating file handler
        agent_id: Unique identifier for this agent instance
        max_bytes: Max size per log file for rotation
        backup_count: Number of backup files to keep
    """
    global _agent_id
    if agent_id:
        _agent_id = agent_id

    # Create formatter
    formatter = JarvisJsonFormatter()

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler (JSON to stderr for easy parsing)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Optional file handler
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


@lru_cache(maxsize=32)
def get_logger(name: str) -> logging.Logger:
    """Get a named logger with agent context.

    Args:
        name: Logger name (e.g., 'jarvis.capture', 'jarvis.sync')

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def set_agent_id(agent_id: str) -> None:
    """Set the agent identifier for log context.

    Args:
        agent_id: Unique identifier for this agent instance
    """
    global _agent_id
    _agent_id = agent_id


# Convenience loggers for common modules
def capture_logger() -> logging.Logger:
    """Get logger for capture events."""
    return get_logger("jarvis.capture")


def sync_logger() -> logging.Logger:
    """Get logger for sync/upload events."""
    return get_logger("jarvis.sync")


def state_logger() -> logging.Logger:
    """Get logger for state changes."""
    return get_logger("jarvis.state")


def config_logger() -> logging.Logger:
    """Get logger for configuration events."""
    return get_logger("jarvis.config")


# --- Audit Event Functions ---
# These provide typed interfaces for common audit events


def log_capture_taken(
    logger: logging.Logger,
    monitor_index: int,
    reason: str,
    file_size: int,
    capture_id: str | None = None,
) -> None:
    """Log a successful capture event.

    Args:
        logger: Logger instance
        monitor_index: Index of the monitor captured
        reason: Why capture was triggered (interval, change)
        file_size: Size of the capture file in bytes
        capture_id: Optional unique capture identifier
    """
    extra = {
        "event": "capture_taken",
        "monitor_index": monitor_index,
        "reason": reason,
        "file_size": file_size,
    }
    if capture_id:
        extra["capture_id"] = capture_id
    logger.info("Capture taken", extra=extra)


def log_capture_skipped(
    logger: logging.Logger,
    reason: str,
    monitor_index: int | None = None,
) -> None:
    """Log a skipped capture event.

    Args:
        logger: Logger instance
        reason: Why capture was skipped (idle, excluded, no_change)
        monitor_index: Optional monitor index
    """
    extra = {
        "event": "capture_skipped",
        "reason": reason,
    }
    if monitor_index is not None:
        extra["monitor_index"] = monitor_index
    logger.debug("Capture skipped", extra=extra)


def log_upload_success(
    logger: logging.Logger,
    capture_id: str,
    server_response_time_ms: float,
) -> None:
    """Log a successful upload.

    Args:
        logger: Logger instance
        capture_id: Unique capture identifier
        server_response_time_ms: Server response time in milliseconds
    """
    logger.info(
        "Upload successful",
        extra={
            "event": "upload_success",
            "capture_id": capture_id,
            "server_response_time_ms": server_response_time_ms,
        },
    )


def log_upload_failed(
    logger: logging.Logger,
    capture_id: str,
    error: str,
    attempt_count: int,
) -> None:
    """Log a failed upload attempt.

    Args:
        logger: Logger instance
        capture_id: Unique capture identifier
        error: Error message (sanitized - no sensitive data)
        attempt_count: Which attempt this was
    """
    logger.warning(
        "Upload failed",
        extra={
            "event": "upload_failed",
            "capture_id": capture_id,
            "error": error,
            "attempt_count": attempt_count,
        },
    )


def log_state_change(
    logger: logging.Logger,
    old_state: str,
    new_state: str,
    trigger: str | None = None,
) -> None:
    """Log a state transition.

    Args:
        logger: Logger instance
        old_state: Previous state
        new_state: New state
        trigger: What triggered the change
    """
    extra = {
        "event": "state_change",
        "old_state": old_state,
        "new_state": new_state,
    }
    if trigger:
        extra["trigger"] = trigger
    logger.info("State changed", extra=extra)


def log_config_change(
    logger: logging.Logger,
    key: str,
    old_value: str | None,
    new_value: str,
) -> None:
    """Log a configuration change.

    Args:
        logger: Logger instance
        key: Configuration key that changed
        old_value: Previous value (None if new key)
        new_value: New value

    Note: Values are logged as strings. Do NOT pass sensitive values like tokens.
    """
    logger.info(
        "Configuration changed",
        extra={
            "event": "config_change",
            "key": key,
            "old_value": old_value,
            "new_value": new_value,
        },
    )
