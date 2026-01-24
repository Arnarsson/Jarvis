"""Timeline API for browsing capture history."""
import logging
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..db.models import Capture

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/timeline", tags=["timeline"])


class TimelineCapture(BaseModel):
    """A capture in the timeline."""

    id: str
    timestamp: datetime
    filepath: str
    width: int
    height: int
    monitor_index: int
    has_ocr: bool = Field(description="Whether OCR text has been extracted")
    text_preview: Optional[str] = Field(default=None, max_length=200)


class TimelineResponse(BaseModel):
    """Timeline response with pagination."""

    captures: list[TimelineCapture]
    total: int
    next_cursor: Optional[str] = Field(
        default=None,
        description="Cursor for next page (ISO timestamp)"
    )
    has_more: bool


class DaySummary(BaseModel):
    """Summary of captures for a single day."""

    date: date
    count: int
    first_capture: datetime
    last_capture: datetime


@router.get("/", response_model=TimelineResponse)
async def get_timeline(
    limit: int = Query(default=50, ge=1, le=200),
    cursor: Optional[str] = Query(default=None, description="ISO timestamp cursor"),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> TimelineResponse:
    """Get captures for timeline browsing.

    Returns captures in reverse chronological order (newest first).
    Uses cursor-based pagination for efficient navigation.

    Query params:
    - limit: Number of captures to return (1-200, default 50)
    - cursor: Timestamp to start from (for pagination)
    - start_date: Filter by start date
    - end_date: Filter by end date
    """
    # Build query
    conditions = []

    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
            conditions.append(Capture.timestamp < cursor_dt)
        except ValueError:
            pass

    if start_date:
        conditions.append(Capture.timestamp >= datetime.combine(start_date, datetime.min.time()))

    if end_date:
        conditions.append(Capture.timestamp <= datetime.combine(end_date, datetime.max.time()))

    # Query captures
    query = (
        select(Capture)
        .where(and_(*conditions) if conditions else True)
        .order_by(Capture.timestamp.desc())
        .limit(limit + 1)  # Fetch one extra to check has_more
    )

    result = await db.execute(query)
    captures = list(result.scalars().all())

    # Check if there are more results
    has_more = len(captures) > limit
    if has_more:
        captures = captures[:limit]

    # Get total count (with filters)
    count_query = select(func.count(Capture.id))
    if start_date:
        count_query = count_query.where(
            Capture.timestamp >= datetime.combine(start_date, datetime.min.time())
        )
    if end_date:
        count_query = count_query.where(
            Capture.timestamp <= datetime.combine(end_date, datetime.max.time())
        )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Build response
    timeline_captures = [
        TimelineCapture(
            id=c.id,
            timestamp=c.timestamp,
            filepath=c.filepath,
            width=c.width,
            height=c.height,
            monitor_index=c.monitor_index,
            has_ocr=bool(c.ocr_text),
            text_preview=c.ocr_text[:200] if c.ocr_text else None,
        )
        for c in captures
    ]

    next_cursor = None
    if has_more and captures:
        next_cursor = captures[-1].timestamp.isoformat()

    return TimelineResponse(
        captures=timeline_captures,
        total=total,
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.get("/days", response_model=list[DaySummary])
async def get_day_summaries(
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    limit: int = Query(default=30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
) -> list[DaySummary]:
    """Get summary of captures grouped by day.

    Useful for calendar view or date picker.
    Returns days in reverse chronological order.
    """
    # Build date filter
    conditions = []
    if start_date:
        conditions.append(Capture.timestamp >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        conditions.append(Capture.timestamp <= datetime.combine(end_date, datetime.max.time()))

    # Group by date
    date_expr = func.date(Capture.timestamp)
    query = (
        select(
            date_expr.label("capture_date"),
            func.count(Capture.id).label("count"),
            func.min(Capture.timestamp).label("first_capture"),
            func.max(Capture.timestamp).label("last_capture"),
        )
        .where(and_(*conditions) if conditions else True)
        .group_by(date_expr)
        .order_by(date_expr.desc())
        .limit(limit)
    )

    result = await db.execute(query)
    rows = result.fetchall()

    return [
        DaySummary(
            date=row.capture_date,
            count=row.count,
            first_capture=row.first_capture,
            last_capture=row.last_capture,
        )
        for row in rows
    ]


@router.get("/{capture_id}")
async def get_capture_detail(
    capture_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get detailed information about a specific capture."""
    result = await db.execute(
        select(Capture).where(Capture.id == capture_id)
    )
    capture = result.scalar_one_or_none()

    if not capture:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Capture not found")

    return {
        "id": capture.id,
        "timestamp": capture.timestamp,
        "filepath": capture.filepath,
        "width": capture.width,
        "height": capture.height,
        "file_size": capture.file_size,
        "monitor_index": capture.monitor_index,
        "ocr_text": capture.ocr_text,
        "processing_status": capture.processing_status,
        "created_at": capture.created_at,
    }
