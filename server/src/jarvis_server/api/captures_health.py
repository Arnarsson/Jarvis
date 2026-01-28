"""Capture health monitoring API endpoints.

Provides health check endpoints specifically for monitoring the capture agent.
This allows external health checks to verify that captures are happening.
"""

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.db.models import Capture
from jarvis_server.db.session import get_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v2/capture", tags=["capture-health"])


# --- Schemas ---


class CaptureHealthResponse(BaseModel):
    """Health check response for capture agent monitoring."""

    status: str  # healthy, degraded, critical
    last_capture_timestamp: datetime | None
    seconds_since_last_capture: float | None
    total_captures: int
    captures_last_hour: int
    captures_last_24h: int


# --- Endpoints ---


@router.get("/health", response_model=CaptureHealthResponse)
async def capture_health_check(
    db: AsyncSession = Depends(get_db),
) -> CaptureHealthResponse:
    """Check capture agent health.

    Returns the timestamp of the most recent capture and statistics
    to help diagnose capture agent issues.

    Status levels:
    - healthy: Last capture < 10 minutes ago
    - degraded: Last capture 10-60 minutes ago
    - critical: Last capture > 60 minutes ago or no captures at all

    This endpoint is called by external health check scripts and monitoring.
    """
    # Get the most recent capture timestamp
    result = await db.execute(
        select(Capture.timestamp)
        .order_by(Capture.timestamp.desc())
        .limit(1)
    )
    last_capture = result.scalar_one_or_none()

    # Calculate seconds since last capture
    now = datetime.now(timezone.utc)
    seconds_since_capture = None
    if last_capture:
        seconds_since_capture = (now - last_capture).total_seconds()

    # Get total capture count
    result = await db.execute(select(func.count(Capture.id)))
    total_captures = result.scalar_one() or 0

    # Get captures in last hour
    from datetime import timedelta
    one_hour_ago = now - timedelta(hours=1)
    result = await db.execute(
        select(func.count(Capture.id))
        .where(Capture.timestamp >= one_hour_ago)
    )
    captures_last_hour = result.scalar_one() or 0

    # Get captures in last 24 hours
    one_day_ago = now - timedelta(days=1)
    result = await db.execute(
        select(func.count(Capture.id))
        .where(Capture.timestamp >= one_day_ago)
    )
    captures_last_24h = result.scalar_one() or 0

    # Determine health status
    status = "critical"  # Default to critical
    if seconds_since_capture is not None:
        if seconds_since_capture < 600:  # 10 minutes
            status = "healthy"
        elif seconds_since_capture < 3600:  # 1 hour
            status = "degraded"
        else:
            status = "critical"
    elif total_captures == 0:
        status = "critical"  # Never captured anything

    logger.info(
        "capture_health_check",
        status=status,
        seconds_since_capture=seconds_since_capture,
        total_captures=total_captures,
    )

    return CaptureHealthResponse(
        status=status,
        last_capture_timestamp=last_capture,
        seconds_since_last_capture=seconds_since_capture,
        total_captures=total_captures,
        captures_last_hour=captures_last_hour,
        captures_last_24h=captures_last_24h,
    )
