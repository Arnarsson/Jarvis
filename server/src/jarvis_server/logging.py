"""Structured logging for Jarvis server.

Uses structlog for rich, contextual JSON logging with request tracking,
audit events, and FastAPI middleware integration.

Usage:
    from jarvis_server.logging import setup_logging, get_logger

    setup_logging("INFO")
    log = get_logger("jarvis_server.api")
    log.info("capture_received", capture_id="abc123", file_size=50000)
"""

from __future__ import annotations

import logging
import sys
import time
import uuid
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Callable

import structlog
from structlog.types import EventDict, Processor

if TYPE_CHECKING:
    from fastapi import Request, Response
    from starlette.middleware.base import RequestResponseEndpoint

# Context variable for request ID
_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    """Get the current request ID from context."""
    return _request_id_var.get()


def set_request_id(request_id: str) -> None:
    """Set the request ID in context."""
    _request_id_var.set(request_id)


def _add_request_id(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add request ID to log event if available."""
    request_id = get_request_id()
    if request_id:
        event_dict["request_id"] = request_id
    return event_dict


def _add_log_level(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add log level to event dict."""
    event_dict["level"] = method_name.upper()
    return event_dict


def _add_timestamp(
    logger: logging.Logger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Add ISO 8601 timestamp to event dict."""
    from datetime import datetime, timezone

    event_dict["timestamp"] = datetime.now(tz=timezone.utc).isoformat()
    return event_dict


def setup_logging(level: str = "INFO") -> None:
    """Configure structlog with JSON rendering.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Shared processors for structlog
    shared_processors: list[Processor] = [
        structlog.stdlib.add_logger_name,
        _add_timestamp,
        _add_log_level,
        _add_request_id,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    # Configure structlog
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level.upper())

    # Configure uvicorn loggers to use our formatting
    for logger_name in ["uvicorn", "uvicorn.error", "uvicorn.access"]:
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.addHandler(handler)
        uvicorn_logger.propagate = False


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Get a bound logger with optional name.

    Args:
        name: Optional logger name (e.g., 'jarvis_server.api')

    Returns:
        Bound structlog logger instance
    """
    if name:
        return structlog.get_logger(name)
    return structlog.get_logger()


class LoggingMiddleware:
    """FastAPI middleware for request logging and request ID tracking.

    Logs request start and completion with timing information.
    Adds request_id to all logs within the request context.
    """

    def __init__(self, app: Any) -> None:
        """Initialize middleware.

        Args:
            app: FastAPI application instance
        """
        self.app = app
        self.logger = get_logger("jarvis_server.middleware")

    async def __call__(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Process request with logging.

        Args:
            request: Incoming request
            call_next: Next middleware/endpoint handler

        Returns:
            Response from handler
        """
        # Generate request ID
        request_id = str(uuid.uuid4())
        set_request_id(request_id)

        # Extract client IP (handles X-Forwarded-For for proxies)
        client_ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        # Log request start
        self.logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            client_ip=client_ip,
        )

        # Process request
        start_time = time.monotonic()
        try:
            response = await call_next(request)
            duration_ms = (time.monotonic() - start_time) * 1000

            # Log request completion
            self.logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

            # Add request ID to response headers for tracing
            response.headers["X-Request-ID"] = request_id

            return response
        except Exception as exc:
            duration_ms = (time.monotonic() - start_time) * 1000
            self.logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration_ms, 2),
                error=str(exc),
            )
            raise
        finally:
            # Clear request ID context
            set_request_id(None)


# --- Audit Event Functions ---
# Typed interfaces for server audit events


def log_capture_received(
    logger: structlog.BoundLogger,
    capture_id: str,
    file_size: int,
    client_ip: str,
) -> None:
    """Log a capture received from agent.

    Args:
        logger: Logger instance
        capture_id: Unique capture identifier
        file_size: Size of the capture file in bytes
        client_ip: Client IP address
    """
    logger.info(
        "capture_received",
        capture_id=capture_id,
        file_size=file_size,
        client_ip=client_ip,
    )


def log_capture_stored(
    logger: structlog.BoundLogger,
    capture_id: str,
    filepath: str,
) -> None:
    """Log a capture stored to filesystem.

    Args:
        logger: Logger instance
        capture_id: Unique capture identifier
        filepath: Path where capture was stored
    """
    logger.info(
        "capture_stored",
        capture_id=capture_id,
        filepath=filepath,
    )


def log_pii_detected(
    logger: structlog.BoundLogger,
    capture_id: str,
    pii_types: list[str],
    count: int,
) -> None:
    """Log PII detected in capture.

    Args:
        logger: Logger instance
        capture_id: Unique capture identifier
        pii_types: Types of PII detected (e.g., ["CREDIT_CARD", "EMAIL"])
        count: Total number of PII instances found
    """
    logger.warning(
        "pii_detected",
        capture_id=capture_id,
        pii_types=pii_types,
        count=count,
    )


def log_api_error(
    logger: structlog.BoundLogger,
    endpoint: str,
    error_type: str,
    message: str,
) -> None:
    """Log an API error.

    Args:
        logger: Logger instance
        endpoint: API endpoint that errored
        error_type: Type of error (e.g., "validation", "internal")
        message: Error message (sanitized - no sensitive data)
    """
    logger.error(
        "api_error",
        endpoint=endpoint,
        error_type=error_type,
        message=message,
    )
