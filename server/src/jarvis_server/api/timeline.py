"""Timeline API for browsing capture history."""
import logging
import re
from collections import Counter
from datetime import datetime, date, timedelta
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


class CaptureSession(BaseModel):
    """A session grouping multiple captures."""

    id: str = Field(description="Session identifier")
    start_time: datetime = Field(description="Session start timestamp")
    end_time: datetime = Field(description="Session end timestamp")
    duration_minutes: int = Field(description="Session duration in minutes")
    primary_app: str = Field(description="Primary application/window")
    project: Optional[str] = Field(default=None, description="Detected project name")
    summary: str = Field(description="Session summary from OCR text")
    capture_count: int = Field(description="Number of captures in session")
    thumbnail_id: str = Field(description="ID of representative capture for thumbnail")
    captures: list[str] = Field(description="List of capture IDs in session")


class TimelineResponse(BaseModel):
    """Timeline response with pagination."""

    captures: list[TimelineCapture]
    total: int
    next_cursor: Optional[str] = Field(
        default=None,
        description="Cursor for next page (ISO timestamp)"
    )
    has_more: bool


class GroupedTimelineResponse(BaseModel):
    """Timeline response with sessions (grouped captures)."""

    sessions: list[CaptureSession]
    total_sessions: int
    total_captures: int
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


# =============================================================================
# Session Clustering Logic
# =============================================================================


def extract_app_from_ocr(ocr_text: Optional[str]) -> str:
    """Extract primary application/window from OCR text.
    
    Uses simple heuristics to detect common app signatures in OCR text.
    """
    if not ocr_text:
        return "Unknown"
    
    text_lower = ocr_text.lower()
    
    # Common app patterns (order matters - check specific before general)
    app_patterns = [
        (r'\bvs\s*code\b|\bvisual\s*studio\s*code\b', "VS Code"),
        (r'\bchrome\b|\bgoogle\s*chrome\b', "Chrome"),
        (r'\bfirefox\b', "Firefox"),
        (r'\bslack\b', "Slack"),
        (r'\bterminal\b|\bbash\b|\bzsh\b', "Terminal"),
        (r'\bnotion\b', "Notion"),
        (r'\bfigma\b', "Figma"),
        (r'\blinear\b', "Linear"),
        (r'\bgithub\b', "GitHub"),
        (r'\bgmail\b', "Gmail"),
        (r'\bjira\b', "Jira"),
        (r'\bpycharm\b', "PyCharm"),
        (r'\bintellijidea\b', "IntelliJ"),
        (r'\bdiscord\b', "Discord"),
        (r'\bspotify\b', "Spotify"),
    ]
    
    for pattern, app_name in app_patterns:
        if re.search(pattern, text_lower):
            return app_name
    
    return "Unknown"


def extract_project_from_ocr(ocr_text: Optional[str]) -> Optional[str]:
    """Extract project name from OCR text.
    
    Looks for common project indicators like folder paths, repo names, etc.
    """
    if not ocr_text:
        return None
    
    # Look for path patterns (e.g., /path/to/RecruitOS)
    path_match = re.search(r'/([A-Z][a-zA-Z0-9_-]+)/', ocr_text)
    if path_match:
        return path_match.group(1)
    
    # Look for window title patterns (ProjectName - App)
    title_match = re.search(r'([A-Z][a-zA-Z0-9_-]+)\s*[-–—]', ocr_text)
    if title_match:
        return title_match.group(1)
    
    return None


def generate_summary_from_ocr(captures: list[Capture]) -> str:
    """Generate a human-readable summary from OCR text.
    
    Uses word frequency and common patterns to create a meaningful summary.
    """
    if not captures:
        return "No activity"
    
    # Collect all OCR text
    all_text = " ".join(c.ocr_text or "" for c in captures)
    if not all_text.strip():
        return "No text detected"
    
    # Extract meaningful tokens (files, keywords, etc.)
    # Find file references
    file_matches = re.findall(r'\b\w+\.(py|js|ts|tsx|jsx|java|cpp|md|txt|json|yaml|yml)\b', all_text, re.IGNORECASE)
    
    # Find common words (excluding noise)
    words = re.findall(r'\b[a-z]{4,}\b', all_text.lower())
    stop_words = {'this', 'that', 'with', 'from', 'have', 'been', 'were', 'their', 'there', 'where', 'when', 'what', 'which', 'about', 'would', 'could', 'should'}
    meaningful_words = [w for w in words if w not in stop_words]
    
    # Count frequencies
    word_freq = Counter(meaningful_words)
    top_words = [word for word, _ in word_freq.most_common(5)]
    
    # Build summary
    summary_parts = []
    
    if file_matches:
        unique_files = list(set(file_matches[:3]))  # Top 3 unique files
        summary_parts.append(f"Working on {', '.join(unique_files)}")
    
    if top_words:
        summary_parts.append(f"Topics: {', '.join(top_words[:3])}")
    
    if not summary_parts:
        return "Activity detected"
    
    return " • ".join(summary_parts)


def cluster_captures_into_sessions(
    captures: list[Capture],
    gap_threshold_minutes: int = 5
) -> list[CaptureSession]:
    """Cluster captures into sessions based on time gaps and app similarity.
    
    Args:
        captures: List of captures sorted by timestamp (descending)
        gap_threshold_minutes: Time gap to consider as session boundary
        
    Returns:
        List of CaptureSession objects
    """
    if not captures:
        return []
    
    # Reverse to process chronologically
    captures_chrono = list(reversed(captures))
    
    sessions = []
    current_session_captures = []
    current_app = None
    session_counter = 0
    
    for i, capture in enumerate(captures_chrono):
        # Extract app from OCR
        capture_app = extract_app_from_ocr(capture.ocr_text)
        
        # Check if we should start a new session
        should_split = False
        
        if not current_session_captures:
            # First capture - start new session
            should_split = False
        else:
            last_capture = current_session_captures[-1]
            time_gap = (capture.timestamp - last_capture.timestamp).total_seconds() / 60
            
            # Split if:
            # 1. Time gap > threshold
            # 2. App changed (unless one is Unknown)
            if time_gap > gap_threshold_minutes:
                should_split = True
            elif capture_app != "Unknown" and current_app != "Unknown" and capture_app != current_app:
                should_split = True
        
        if should_split and current_session_captures:
            # Save current session
            sessions.append(_create_session(current_session_captures, session_counter))
            session_counter += 1
            current_session_captures = []
            current_app = None
        
        # Add to current session
        current_session_captures.append(capture)
        if capture_app != "Unknown":
            current_app = capture_app
    
    # Don't forget the last session
    if current_session_captures:
        sessions.append(_create_session(current_session_captures, session_counter))
    
    # Return in reverse chronological order (newest first)
    return list(reversed(sessions))


def _create_session(captures: list[Capture], session_id: int) -> CaptureSession:
    """Create a CaptureSession from a list of captures."""
    start_time = captures[0].timestamp
    end_time = captures[-1].timestamp
    duration_minutes = int((end_time - start_time).total_seconds() / 60)
    
    # Determine primary app (most common non-Unknown app)
    apps = [extract_app_from_ocr(c.ocr_text) for c in captures]
    app_counts = Counter(app for app in apps if app != "Unknown")
    primary_app = app_counts.most_common(1)[0][0] if app_counts else "Unknown"
    
    # Extract project (from any capture in session)
    project = None
    for capture in captures:
        proj = extract_project_from_ocr(capture.ocr_text)
        if proj:
            project = proj
            break
    
    # Generate summary
    summary = generate_summary_from_ocr(captures)
    
    # Choose middle capture as thumbnail (better representative)
    thumbnail_idx = len(captures) // 2
    thumbnail_id = captures[thumbnail_idx].id
    
    return CaptureSession(
        id=f"session_{session_id}_{int(start_time.timestamp())}",
        start_time=start_time,
        end_time=end_time,
        duration_minutes=max(1, duration_minutes),  # At least 1 minute
        primary_app=primary_app,
        project=project,
        summary=summary[:200],  # Cap summary length
        capture_count=len(captures),
        thumbnail_id=thumbnail_id,
        captures=[c.id for c in captures],
    )


# =============================================================================
# API Routes
# =============================================================================


@router.get("/")
async def get_timeline(
    limit: int = Query(default=50, ge=1, le=200),
    cursor: Optional[str] = Query(default=None, description="ISO timestamp cursor"),
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    grouped: bool = Query(default=False, description="Group captures into sessions"),
    db: AsyncSession = Depends(get_db),
) -> TimelineResponse | GroupedTimelineResponse:
    """Get captures for timeline browsing.

    Returns captures in reverse chronological order (newest first).
    Uses cursor-based pagination for efficient navigation.

    Query params:
    - limit: Number of captures/sessions to return (1-200, default 50)
    - cursor: Timestamp to start from (for pagination)
    - start_date: Filter by start date
    - end_date: Filter by end date
    - grouped: If true, returns sessions instead of individual captures
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

    if grouped:
        # For grouped mode, fetch more captures to ensure proper session formation
        # We'll fetch captures and then cluster them
        query = (
            select(Capture)
            .where(and_(*conditions) if conditions else True)
            .order_by(Capture.timestamp.desc())
            .limit(500)  # Fetch more for proper clustering
        )
        
        result = await db.execute(query)
        captures = list(result.scalars().all())
        
        # Cluster into sessions
        sessions = cluster_captures_into_sessions(captures)
        
        # Apply limit to sessions
        has_more = len(sessions) > limit
        if has_more:
            sessions = sessions[:limit]
        
        # Get total counts
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
        total_captures = total_result.scalar() or 0
        
        next_cursor = None
        if has_more and sessions:
            next_cursor = sessions[-1].end_time.isoformat()
        
        return GroupedTimelineResponse(
            sessions=sessions,
            total_sessions=len(sessions),
            total_captures=total_captures,
            next_cursor=next_cursor,
            has_more=has_more,
        )
    
    else:
        # Original ungrouped mode
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
