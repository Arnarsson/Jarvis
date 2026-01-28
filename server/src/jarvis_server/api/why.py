"""Why + Confidence API - fetch detailed context for suggestions.

Provides the GET /api/why/{suggestion_type}/{id} endpoint to retrieve
full explanation context with sources for any Jarvis suggestion.
"""

from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.api.helpers import (
    build_why_from_calendar,
    build_why_from_capture,
    build_why_from_conversation,
    build_why_from_pattern,
)
from jarvis_server.api.models import WhyPayload
from jarvis_server.calendar.models import CalendarEvent, Meeting
from jarvis_server.db.models import Capture, ConversationRecord, DetectedPattern
from jarvis_server.db.session import get_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/why", tags=["why"])


@router.get("/{suggestion_type}/{id}", response_model=WhyPayload)
async def get_why_context(
    suggestion_type: str = Path(
        ...,
        description="Type of suggestion: pattern, meeting, capture, conversation, calendar"
    ),
    id: str = Path(..., description="ID of the suggestion"),
    db: AsyncSession = Depends(get_db),
) -> WhyPayload:
    """Fetch full Why + Confidence context for a suggestion.
    
    Returns detailed explanation including:
    - Plain English reasons why this suggestion was made
    - Confidence score
    - Links to all source data (emails, captures, calendar, etc.)
    
    Supports suggestion types:
    - pattern: Detected behavioral pattern
    - meeting: Meeting or event
    - capture: Screen capture
    - conversation: AI conversation
    - calendar: Calendar event
    """
    try:
        if suggestion_type == "pattern":
            return await _get_pattern_why(id, db)
        elif suggestion_type == "meeting":
            return await _get_meeting_why(id, db)
        elif suggestion_type == "capture":
            return await _get_capture_why(id, db)
        elif suggestion_type == "conversation":
            return await _get_conversation_why(id, db)
        elif suggestion_type == "calendar":
            return await _get_calendar_why(id, db)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown suggestion type: {suggestion_type}. "
                       f"Must be: pattern, meeting, capture, conversation, or calendar"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "why_context_fetch_failed",
            suggestion_type=suggestion_type,
            id=id,
            error=str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch why context: {str(e)}"
        )


async def _get_pattern_why(pattern_id: str, db: AsyncSession) -> WhyPayload:
    """Build Why context for a detected pattern."""
    result = await db.execute(
        select(DetectedPattern).where(DetectedPattern.id == pattern_id)
    )
    pattern = result.scalar_one_or_none()
    
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")
    
    # Build reasons based on pattern metadata
    reasons = [
        f"Detected {pattern.frequency} times",
        f"Pattern type: {pattern.pattern_type.replace('_', ' ').title()}",
    ]
    
    if pattern.suggested_action:
        reasons.append(f"Suggested action available")
    
    # Confidence based on frequency (rough heuristic)
    confidence = min(0.5 + (pattern.frequency * 0.05), 0.95)
    
    logger.info("pattern_why_fetched", id=pattern_id, frequency=pattern.frequency)
    
    return build_why_from_pattern(
        pattern_id=pattern.id,
        pattern_description=pattern.description,
        pattern_last_seen=pattern.last_seen,
        reasons=reasons,
        confidence=confidence,
        source_conversation_ids=pattern.conversation_ids
    )


async def _get_meeting_why(meeting_id: str, db: AsyncSession) -> WhyPayload:
    """Build Why context for a meeting."""
    result = await db.execute(
        select(Meeting).where(Meeting.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    reasons = [f"Meeting detected on {meeting.platform or 'unknown platform'}"]
    
    # Check if linked to calendar event
    calendar_event = None
    if meeting.calendar_event_id:
        result = await db.execute(
            select(CalendarEvent).where(CalendarEvent.id == meeting.calendar_event_id)
        )
        calendar_event = result.scalar_one_or_none()
        if calendar_event:
            reasons.append(f"Scheduled event: {calendar_event.summary}")
    
    confidence = 0.9 if calendar_event else 0.7
    
    sources = [{
        "type": "calendar" if calendar_event else "capture",
        "id": meeting.id,
        "timestamp": meeting.detected_at,
        "snippet": calendar_event.summary if calendar_event else f"Meeting on {meeting.platform}",
        "url": f"/meetings/{meeting.id}"
    }]
    
    logger.info("meeting_why_fetched", id=meeting_id, has_calendar_link=bool(calendar_event))
    
    from jarvis_server.api.helpers import build_why_payload
    return build_why_payload(reasons, confidence, sources)


async def _get_capture_why(capture_id: str, db: AsyncSession) -> WhyPayload:
    """Build Why context for a capture."""
    result = await db.execute(
        select(Capture).where(Capture.id == capture_id)
    )
    capture = result.scalar_one_or_none()
    
    if not capture:
        raise HTTPException(status_code=404, detail="Capture not found")
    
    reasons = [
        f"Screen capture from {capture.timestamp.strftime('%Y-%m-%d %H:%M')}",
        f"Monitor {capture.monitor_index}",
    ]
    
    if capture.ocr_text:
        reasons.append("Contains extracted text")
    
    # Basic confidence
    confidence = 0.6 if capture.ocr_text else 0.4
    
    logger.info("capture_why_fetched", id=capture_id, has_text=bool(capture.ocr_text))
    
    return build_why_from_capture(
        capture_id=capture.id,
        capture_text=capture.ocr_text or "",
        capture_timestamp=capture.timestamp,
        reasons=reasons,
        confidence=confidence
    )


async def _get_conversation_why(conversation_id: str, db: AsyncSession) -> WhyPayload:
    """Build Why context for a conversation."""
    result = await db.execute(
        select(ConversationRecord).where(ConversationRecord.id == conversation_id)
    )
    conversation = result.scalar_one_or_none()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    reasons = [
        f"Conversation from {conversation.source}",
        f"{conversation.message_count} messages",
    ]
    
    if conversation.conversation_date:
        days_ago = (datetime.now(timezone.utc) - conversation.conversation_date).days
        if days_ago < 7:
            reasons.append("Recent conversation")
    
    # Higher confidence for recent conversations
    confidence = 0.8 if conversation.conversation_date and days_ago < 7 else 0.6
    
    logger.info("conversation_why_fetched", id=conversation_id, source=conversation.source)
    
    return build_why_from_conversation(
        conversation_id=conversation.id,
        conversation_title=conversation.title,
        conversation_date=conversation.conversation_date or conversation.imported_at,
        reasons=reasons,
        confidence=confidence
    )


async def _get_calendar_why(event_id: str, db: AsyncSession) -> WhyPayload:
    """Build Why context for a calendar event."""
    result = await db.execute(
        select(CalendarEvent).where(CalendarEvent.id == event_id)
    )
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(status_code=404, detail="Calendar event not found")
    
    reasons = [
        f"Scheduled event: {event.summary}",
    ]
    
    # Check if event is soon
    if event.start_time:
        time_until = event.start_time - datetime.now(timezone.utc)
        if time_until.total_seconds() < 3600:  # Less than 1 hour
            reasons.append("Starting soon")
            confidence = 0.95
        elif time_until.total_seconds() < 86400:  # Less than 1 day
            reasons.append("Today")
            confidence = 0.85
        else:
            confidence = 0.7
    else:
        confidence = 0.5
    
    logger.info("calendar_why_fetched", id=event_id, summary=event.summary)
    
    return build_why_from_calendar(
        event_id=event.id,
        event_title=event.summary or "Untitled Event",
        event_start=event.start_time or datetime.now(timezone.utc),
        reasons=reasons,
        confidence=confidence
    )
