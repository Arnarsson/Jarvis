"""Meeting Brief API - Generate contextual meeting preparation briefs."""

from __future__ import annotations

import structlog
from datetime import datetime, timedelta, timezone
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.db.session import get_db
from jarvis_server.db.models import CalendarEvent, EmailMessage, Promise, Capture

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/meeting", tags=["meeting-brief"])


class Touchpoint(BaseModel):
    """A recent interaction/touchpoint with an attendee."""
    type: str  # email, capture, task, calendar
    date: str  # ISO date string
    summary: str
    snippet: str | None = None
    source_id: str | None = None


class OpenLoop(BaseModel):
    """An open task or commitment involving the attendee."""
    description: str
    owner: str  # "you" or attendee name
    due_date: str | None = None  # ISO date string
    status: str
    source: str | None = None


class SharedFile(BaseModel):
    """A shared file/document."""
    name: str
    url: str | None = None
    last_modified: str | None = None  # ISO date string


class MeetingDetails(BaseModel):
    """Meeting basic details."""
    title: str
    start_time: str  # ISO datetime string
    attendees: list[str]  # List of email addresses
    location: str | None = None


class ContextData(BaseModel):
    """Contextual information about the meeting."""
    last_touchpoints: list[Touchpoint]
    open_loops: list[OpenLoop]
    shared_files: list[SharedFile]


class WhyPayload(BaseModel):
    """Explanation of why this brief was generated and its relevance."""
    reasons: list[str]
    confidence: float  # 0-1
    sources: list[str]


class MeetingBriefResponse(BaseModel):
    """Complete meeting brief response matching spec."""
    meeting: MeetingDetails
    context: ContextData
    suggested_talking_points: list[str]
    why: WhyPayload


async def _get_attendee_emails(event_id: str, db: AsyncSession) -> list[dict[str, str]]:
    """Extract attendee emails from a calendar event."""
    result = await db.execute(
        select(CalendarEvent).where(CalendarEvent.event_id == event_id)
    )
    event = result.scalar_one_or_none()
    
    if not event or not event.attendees:
        return []
    
    # Parse attendees JSON
    attendees_list = []
    for attendee in event.attendees:
        if isinstance(attendee, dict) and attendee.get('email'):
            attendees_list.append({
                'name': attendee.get('displayName', attendee.get('email', '').split('@')[0]),
                'email': attendee['email']
            })
    
    return attendees_list


async def _get_recent_touchpoints(
    attendee_email: str, 
    lookback_days: int,
    db: AsyncSession
) -> list[Touchpoint]:
    """Get recent interactions with a specific attendee."""
    touchpoints = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    
    # Recent emails with this attendee
    email_result = await db.execute(
        select(EmailMessage)
        .where(
            and_(
                EmailMessage.received_at >= cutoff,
                or_(
                    EmailMessage.sender.ilike(f"%{attendee_email}%"),
                    EmailMessage.recipient.ilike(f"%{attendee_email}%")
                )
            )
        )
        .order_by(EmailMessage.received_at.desc())
        .limit(3)
    )
    
    for email in email_result.scalars():
        touchpoints.append(Touchpoint(
            type="email",
            date=email.received_at.date().isoformat(),
            summary=email.subject or "Email",
            snippet=email.snippet[:200] if email.snippet else None,
            source_id=f"email_{email.id}"
        ))
    
    # Recent captures mentioning the attendee
    # Look for captures that contain attendee name or email
    attendee_name_parts = attendee_email.split('@')[0].split('.')
    if attendee_name_parts:
        name_query = attendee_name_parts[0]
        capture_result = await db.execute(
            select(Capture)
            .where(
                and_(
                    Capture.created_at >= cutoff,
                    or_(
                        Capture.window_title.ilike(f"%{name_query}%"),
                        Capture.text_content.ilike(f"%{name_query}%") if hasattr(Capture, 'text_content') else False
                    )
                )
            )
            .order_by(Capture.created_at.desc())
            .limit(2)
        )
        
        for capture in capture_result.scalars():
            touchpoints.append(Touchpoint(
                type="capture",
                date=capture.created_at.date().isoformat(),
                summary=f"Activity: {capture.window_title or 'Work session'}",
                snippet=capture.window_title[:200] if capture.window_title else None,
                source_id=f"capture_{capture.id}"
            ))
    
    return touchpoints[:5]  # Return top 5 most recent


async def _get_open_loops(
    attendee_email: str,
    db: AsyncSession
) -> list[OpenLoop]:
    """Get open tasks and commitments involving the attendee."""
    loops = []
    
    # Get pending promises involving this attendee
    promise_result = await db.execute(
        select(Promise)
        .where(
            and_(
                Promise.status.in_(['pending', 'overdue']),
                or_(
                    Promise.promiser.ilike(f"%{attendee_email}%"),
                    Promise.promisee.ilike(f"%{attendee_email}%")
                )
            )
        )
        .order_by(Promise.due_date.asc())
        .limit(5)
    )
    
    for promise in promise_result.scalars():
        loops.append(OpenLoop(
            description=promise.description,
            owner="you" if promise.promiser == "you" else promise.promiser,
            due_date=promise.due_date.isoformat() if promise.due_date else None,
            status=promise.status,
            source=f"promise_{promise.id}"
        ))
    
    return loops


def _generate_talking_points(
    touchpoints: list[Touchpoint],
    open_loops: list[OpenLoop],
    attendees: list[str],
    meeting_title: str
) -> list[str]:
    """Generate AI-powered talking point suggestions."""
    points = []
    
    # Heuristic-based suggestions (would be replaced with LLM in production)
    
    # If there are overdue commitments, flag them
    overdue_loops = [loop for loop in open_loops if loop.status == 'overdue']
    if overdue_loops:
        for loop in overdue_loops[:2]:  # Top 2 overdue items
            points.append(f"Follow up on overdue: {loop.description}")
    
    # If there were recent touchpoints, suggest discussing them
    if len(touchpoints) >= 2:
        recent_topics = [t.summary for t in touchpoints[:2]]
        points.append(f"Continue discussion: {recent_topics[0]}")
    
    # Suggest addressing any pending commitments
    pending_loops = [loop for loop in open_loops if loop.status == 'pending']
    if pending_loops:
        points.append(f"Address pending commitment: {pending_loops[0].description}")
    
    # Generic meeting prep point if nothing else
    if not points:
        points.append("Review meeting agenda and objectives")
        points.append("Align on next steps")
    
    return points[:5]  # Top 5 suggestions


def _generate_why_payload(
    touchpoints: list[Touchpoint],
    open_loops: list[OpenLoop],
    meeting_time: datetime
) -> WhyPayload:
    """Generate the 'why' explanation payload."""
    reasons = []
    sources = []
    confidence = 0.7  # Base confidence
    
    # Calculate time until meeting
    now = datetime.now(timezone.utc)
    time_until = meeting_time - now
    minutes_until = int(time_until.total_seconds() / 60)
    
    if minutes_until <= 60:
        reasons.append(f"Meeting in {minutes_until} minutes")
        confidence = max(confidence, 0.9)
    elif minutes_until <= 180:
        hours_until = minutes_until // 60
        reasons.append(f"Meeting in {hours_until} hours")
        confidence = max(confidence, 0.8)
    else:
        days_until = minutes_until // 1440
        reasons.append(f"Meeting in {days_until} days")
    
    # Count overdue commitments
    overdue_count = len([loop for loop in open_loops if loop.status == 'overdue'])
    if overdue_count > 0:
        reasons.append(f"{overdue_count} overdue commitment{'s' if overdue_count > 1 else ''}")
        confidence = max(confidence, 0.85)
        sources.extend([loop.source for loop in open_loops if loop.status == 'overdue' and loop.source])
    
    # Note recent activity
    if len(touchpoints) >= 3:
        reasons.append(f"{len(touchpoints)} recent interactions")
        sources.extend([tp.source_id for tp in touchpoints if tp.source_id])
    
    # Note any pending loops
    pending_count = len([loop for loop in open_loops if loop.status == 'pending'])
    if pending_count > 0:
        reasons.append(f"{pending_count} pending action{'s' if pending_count > 1 else ''}")
        sources.extend([loop.source for loop in open_loops if loop.status == 'pending' and loop.source])
    
    # If no specific reasons, provide a default
    if not reasons:
        reasons.append("Upcoming meeting requires preparation")
        confidence = 0.5
    
    return WhyPayload(
        reasons=reasons,
        confidence=min(confidence, 1.0),  # Cap at 1.0
        sources=list(set(sources[:10]))  # Unique sources, max 10
    )


@router.get("/{event_id}/brief", response_model=MeetingBriefResponse)
async def get_meeting_brief(
    event_id: str,
    lookback_days: int = Query(default=30, ge=1, le=90),
    db: AsyncSession = Depends(get_db)
) -> MeetingBriefResponse:
    """
    Generate a comprehensive meeting brief for a specific calendar event.
    
    This is the P0 Pre-Meeting Brief API endpoint that provides one-tap meeting
    preparation with context, touchpoints, open loops, and suggested talking points.
    
    Args:
        event_id: Google Calendar event ID
        lookback_days: How many days back to search for touchpoints (default 30)
        db: Database session
        
    Returns:
        Complete meeting brief with context, talking points, and why payload
    """
    logger.info("generating_meeting_brief", event_id=event_id)
    
    # Get the calendar event
    result = await db.execute(
        select(CalendarEvent).where(CalendarEvent.event_id == event_id)
    )
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    # Extract attendees
    attendee_emails = await _get_attendee_emails(event_id, db)
    attendee_email_list = [a['email'] for a in attendee_emails]
    
    # Aggregate context across all attendees
    all_touchpoints = []
    all_open_loops = []
    
    for attendee in attendee_emails:
        touchpoints = await _get_recent_touchpoints(
            attendee['email'], 
            lookback_days, 
            db
        )
        open_loops = await _get_open_loops(attendee['email'], db)
        
        all_touchpoints.extend(touchpoints)
        all_open_loops.extend(open_loops)
    
    # Sort touchpoints by date (most recent first)
    all_touchpoints.sort(key=lambda t: t.date, reverse=True)
    
    # Deduplicate and limit
    seen_sources = set()
    unique_touchpoints = []
    for tp in all_touchpoints:
        if tp.source_id not in seen_sources:
            unique_touchpoints.append(tp)
            seen_sources.add(tp.source_id)
    
    # Limit to most recent/relevant
    final_touchpoints = unique_touchpoints[:10]
    final_open_loops = all_open_loops[:10]
    
    # Generate talking points
    talking_points = _generate_talking_points(
        final_touchpoints,
        final_open_loops,
        attendee_email_list,
        event.summary
    )
    
    # Generate why payload
    why = _generate_why_payload(
        final_touchpoints,
        final_open_loops,
        event.start_time
    )
    
    # Build meeting details
    meeting = MeetingDetails(
        title=event.summary,
        start_time=event.start_time.isoformat(),
        attendees=attendee_email_list,
        location=event.location if hasattr(event, 'location') else None
    )
    
    # Build context data
    context = ContextData(
        last_touchpoints=final_touchpoints,
        open_loops=final_open_loops,
        shared_files=[]  # TODO: Implement file tracking from captures/Drive
    )
    
    logger.info(
        "meeting_brief_generated",
        event_id=event_id,
        touchpoints_count=len(final_touchpoints),
        open_loops_count=len(final_open_loops),
        talking_points_count=len(talking_points)
    )
    
    return MeetingBriefResponse(
        meeting=meeting,
        context=context,
        suggested_talking_points=talking_points,
        why=why
    )


@router.get("/upcoming/preview")
async def get_upcoming_meeting_previews(
    minutes_ahead: int = Query(default=15, ge=5, le=120),
    db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    """
    Get a list of meetings that need prep in the next N minutes.
    Useful for triggering notifications.
    
    Args:
        minutes_ahead: How many minutes ahead to look (default 15)
        db: Database session
        
    Returns:
        List of meetings needing prep with basic context
    """
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(minutes=minutes_ahead)
    
    result = await db.execute(
        select(CalendarEvent)
        .where(
            and_(
                CalendarEvent.start_time > now,
                CalendarEvent.start_time <= cutoff,
                CalendarEvent.status == 'confirmed'
            )
        )
        .order_by(CalendarEvent.start_time.asc())
    )
    
    meetings = []
    for event in result.scalars():
        minutes_until = int((event.start_time - now).total_seconds() / 60)
        attendee_count = len(event.attendees) if event.attendees else 0
        
        meetings.append({
            'event_id': event.event_id,
            'title': event.summary,
            'start_time': event.start_time.isoformat(),
            'minutes_until': minutes_until,
            'attendee_count': attendee_count,
            'needs_prep': True,  # All in this list need prep
            'brief_url': f"/meeting-brief/{event.event_id}"
        })
    
    return {
        'meetings': meetings,
        'count': len(meetings),
        'checked_at': now.isoformat()
    }
