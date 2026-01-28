"""Bridge API for Clawdbot ↔ Jarvis integration.

Provides simple REST endpoints for Clawdbot to query Jarvis data:
- Search memory (captures, emails, conversations)
- Get daily briefing
- Fetch pending decisions
- Get follow-up items
- Get project context
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, or_, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.db.session import get_db
from jarvis_server.email.models import EmailMessage
from jarvis_server.calendar.models import CalendarEvent
from jarvis_server.search.hybrid import hybrid_search
from jarvis_server.search.schemas import SearchRequest

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v2/bridge", tags=["bridge"])


# Response Models
class SearchResultItem(BaseModel):
    """Single search result."""
    type: str
    title: str
    snippet: str
    date: str
    source: str
    relevance_score: float


class BriefingEvent(BaseModel):
    """Calendar event for briefing."""
    summary: str
    start_time: str
    end_time: str
    location: str | None = None
    attendees_count: int = 0


class BriefingEmail(BaseModel):
    """Priority email for briefing."""
    subject: str | None
    from_address: str | None
    from_name: str | None
    snippet: str | None
    date_sent: str


class DecisionItem(BaseModel):
    """Pending decision item."""
    id: str
    subject: str | None
    from_address: str | None
    from_name: str | None
    date_sent: str
    snippet: str | None
    urgency: str
    action_phrases: list[str]


class FollowUpItem(BaseModel):
    """Follow-up item from email."""
    id: str
    subject: str | None
    from_address: str | None
    from_name: str | None
    date_sent: str
    promise: str
    days_since: int


class ContextTimelineItem(BaseModel):
    """Timeline item for project context."""
    type: str
    date: str
    title: str
    content: str


# Response containers
class SearchResponse(BaseModel):
    """Search results."""
    results: list[SearchResultItem]
    total: int


class BriefingResponse(BaseModel):
    """Daily briefing."""
    greeting: str
    events: list[BriefingEvent]
    priority_emails: list[BriefingEmail]
    decisions: list[DecisionItem]
    daily3_status: str


class DecisionsResponse(BaseModel):
    """Pending decisions."""
    decisions: list[DecisionItem]
    count: int


class FollowUpsResponse(BaseModel):
    """Follow-up items."""
    followups: list[FollowUpItem]
    count: int


class ContextResponse(BaseModel):
    """Project context."""
    project: str
    timeline: list[ContextTimelineItem]
    summary: str


# Endpoints

@router.get("/search", response_model=SearchResponse)
async def bridge_search(
    q: str = Query(..., description="Search query"),
    limit: int = Query(5, ge=1, le=20, description="Max results"),
) -> SearchResponse:
    """Search Jarvis memory (conversations + emails + captures).
    
    Uses semantic search over the vector store plus email database.
    """
    try:
        # Search vector store (captures)
        search_req = SearchRequest(query=q, limit=limit)
        vector_results = hybrid_search(search_req)
        
        results = []
        for r in vector_results:
            results.append(SearchResultItem(
                type="capture",
                title=r.source or "Capture",
                snippet=r.text_preview[:200] if r.text_preview else "",
                date=r.timestamp.isoformat() if r.timestamp else "",
                source=r.source or "unknown",
                relevance_score=r.score,
            ))
        
        logger.info("bridge_search_completed", query=q, results=len(results))
        return SearchResponse(results=results, total=len(results))
        
    except Exception as e:
        logger.error("bridge_search_failed", query=q, error=str(e))
        raise HTTPException(status_code=500, detail="Search failed")


@router.get("/briefing", response_model=BriefingResponse)
async def bridge_briefing(
    db: AsyncSession = Depends(get_db),
) -> BriefingResponse:
    """Generate today's briefing.
    
    Includes:
    - Calendar events for today
    - Priority unread emails (last 24h)
    - Pending decisions
    - Daily 3 status placeholder
    """
    try:
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Get today's calendar events
        events_result = await db.execute(
            select(CalendarEvent)
            .where(
                and_(
                    CalendarEvent.start_time >= today_start,
                    CalendarEvent.start_time <= today_end,
                    CalendarEvent.status == "confirmed"
                )
            )
            .order_by(CalendarEvent.start_time)
        )
        events = events_result.scalars().all()
        
        briefing_events = []
        for event in events:
            attendees_count = 0
            if event.attendees_json:
                import json
                try:
                    attendees = json.loads(event.attendees_json)
                    attendees_count = len(attendees) if isinstance(attendees, list) else 0
                except:
                    pass
            
            briefing_events.append(BriefingEvent(
                summary=event.summary,
                start_time=event.start_time.isoformat(),
                end_time=event.end_time.isoformat(),
                location=event.location,
                attendees_count=attendees_count,
            ))
        
        # Get priority unread emails (last 24h)
        yesterday = now - timedelta(days=1)
        priority_result = await db.execute(
            select(EmailMessage)
            .where(
                and_(
                    EmailMessage.category == "priority",
                    EmailMessage.is_unread == True,
                    EmailMessage.date_sent >= yesterday
                )
            )
            .order_by(EmailMessage.date_sent.desc())
            .limit(5)
        )
        priority_emails_data = priority_result.scalars().all()
        
        priority_emails = [
            BriefingEmail(
                subject=email.subject,
                from_address=email.from_address,
                from_name=email.from_name,
                snippet=email.snippet,
                date_sent=email.date_sent.isoformat(),
            )
            for email in priority_emails_data
        ]
        
        # Get pending decisions
        decisions = await _get_decisions(db, limit=3)
        
        # Generate greeting
        hour = now.hour
        if hour < 12:
            greeting = f"Good morning! Today is {now.strftime('%A, %B %d')}."
        elif hour < 17:
            greeting = f"Good afternoon! Today is {now.strftime('%A, %B %d')}."
        else:
            greeting = f"Good evening! Today is {now.strftime('%A, %B %d')}."
        
        logger.info("bridge_briefing_generated", events=len(briefing_events), emails=len(priority_emails))
        
        return BriefingResponse(
            greeting=greeting,
            events=briefing_events,
            priority_emails=priority_emails,
            decisions=decisions,
            daily3_status="Not yet configured",  # Placeholder
        )
        
    except Exception as e:
        logger.error("bridge_briefing_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Briefing generation failed")


@router.get("/decisions", response_model=DecisionsResponse)
async def bridge_decisions(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> DecisionsResponse:
    """Get pending decisions from emails.
    
    Scans for action language: approve, confirm, decide, RSVP, deadline, etc.
    """
    try:
        decisions = await _get_decisions(db, limit=limit)
        logger.info("bridge_decisions_retrieved", count=len(decisions))
        return DecisionsResponse(decisions=decisions, count=len(decisions))
        
    except Exception as e:
        logger.error("bridge_decisions_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve decisions")


@router.get("/followups", response_model=FollowUpsResponse)
async def bridge_followups(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> FollowUpsResponse:
    """Get follow-up items from emails.
    
    Detects promise language: "I will", "will send", "will follow up", etc.
    """
    try:
        followup_phrases = [
            "I will",
            "will send",
            "will follow up",
            "will get back",
            "will reach out",
            "will let you know",
            "will update",
            "will share",
            "I'll",
        ]
        
        # Build OR conditions
        conditions = []
        for phrase in followup_phrases:
            conditions.append(EmailMessage.body_text.ilike(f"%{phrase}%"))
        
        # Query for emails with promise language
        result = await db.execute(
            select(EmailMessage)
            .where(or_(*conditions))
            .order_by(EmailMessage.date_sent.desc())
            .limit(limit)
        )
        messages = result.scalars().all()
        
        followups = []
        for msg in messages:
            # Extract the promise text
            body = msg.body_text or ""
            promise = ""
            for phrase in followup_phrases:
                if phrase.lower() in body.lower():
                    # Find the sentence containing the phrase
                    idx = body.lower().find(phrase.lower())
                    start = max(0, idx - 50)
                    end = min(len(body), idx + 150)
                    promise = body[start:end].strip()
                    break
            
            # Calculate days since
            from datetime import timezone as tz
            now = datetime.now(tz.utc)
            date_sent = msg.date_sent
            if date_sent.tzinfo is None:
                date_sent = date_sent.replace(tzinfo=tz.utc)
            days_since = (now - date_sent).days
            
            followups.append(FollowUpItem(
                id=msg.id,
                subject=msg.subject,
                from_address=msg.from_address,
                from_name=msg.from_name,
                date_sent=msg.date_sent.isoformat(),
                promise=promise or msg.snippet or "",
                days_since=days_since,
            ))
        
        logger.info("bridge_followups_retrieved", count=len(followups))
        return FollowUpsResponse(followups=followups, count=len(followups))
        
    except Exception as e:
        logger.error("bridge_followups_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve follow-ups")


@router.get("/context/{project_name}", response_model=ContextResponse)
async def bridge_context(
    project_name: str,
    db: AsyncSession = Depends(get_db),
) -> ContextResponse:
    """Get project context: captures, emails, events related to a project.
    
    Aggregates all mentions of the project across data sources.
    """
    try:
        timeline = []
        
        # Search emails mentioning the project
        email_result = await db.execute(
            select(EmailMessage)
            .where(
                or_(
                    EmailMessage.subject.ilike(f"%{project_name}%"),
                    EmailMessage.body_text.ilike(f"%{project_name}%")
                )
            )
            .order_by(EmailMessage.date_sent.desc())
            .limit(10)
        )
        emails = email_result.scalars().all()
        
        for email in emails:
            timeline.append(ContextTimelineItem(
                type="email",
                date=email.date_sent.isoformat(),
                title=email.subject or "(No subject)",
                content=email.snippet or "",
            ))
        
        # Search calendar events
        event_result = await db.execute(
            select(CalendarEvent)
            .where(
                or_(
                    CalendarEvent.summary.ilike(f"%{project_name}%"),
                    CalendarEvent.description.ilike(f"%{project_name}%")
                )
            )
            .order_by(CalendarEvent.start_time.desc())
            .limit(10)
        )
        events = event_result.scalars().all()
        
        for event in events:
            timeline.append(ContextTimelineItem(
                type="event",
                date=event.start_time.isoformat(),
                title=event.summary,
                content=event.description or "",
            ))
        
        # Sort timeline by date
        timeline.sort(key=lambda x: x.date, reverse=True)
        
        # Generate summary
        summary = f"Found {len(timeline)} items related to {project_name}"
        
        logger.info("bridge_context_retrieved", project=project_name, items=len(timeline))
        return ContextResponse(
            project=project_name,
            timeline=timeline,
            summary=summary,
        )
        
    except Exception as e:
        logger.error("bridge_context_failed", project=project_name, error=str(e))
        raise HTTPException(status_code=500, detail="Failed to retrieve context")


# Helper functions

async def _get_decisions(db: AsyncSession, limit: int = 10) -> list[DecisionItem]:
    """Internal helper to get pending decisions."""
    decision_phrases = [
        "please approve",
        "need your decision",
        "waiting for confirmation",
        "action required",
        "please confirm",
        "your approval",
        "sign off",
        "need to decide",
        "pending your",
        "RSVP",
        "deadline",
    ]
    
    # Build OR conditions
    conditions = []
    for phrase in decision_phrases:
        conditions.append(EmailMessage.subject.ilike(f"%{phrase}%"))
        conditions.append(EmailMessage.body_text.ilike(f"%{phrase}%"))
    
    # Query for decision-requiring emails
    result = await db.execute(
        select(EmailMessage)
        .where(or_(*conditions))
        .order_by(EmailMessage.date_sent.desc())
        .limit(limit)
    )
    messages = result.scalars().all()
    
    decisions = []
    for msg in messages:
        # Determine urgency
        subject_lower = (msg.subject or "").lower()
        urgency = "normal"
        if any(prefix in subject_lower for prefix in ["re:", "fw:"]):
            urgency = "high"
        elif any(word in subject_lower for word in ["urgent", "asap", "immediate"]):
            urgency = "high"
        
        # Extract matching phrases
        action_phrases = []
        combined = f"{msg.subject or ''} {msg.body_text or ''}".lower()
        for phrase in decision_phrases:
            if phrase in combined:
                action_phrases.append(phrase)
        
        decisions.append(DecisionItem(
            id=msg.id,
            subject=msg.subject,
            from_address=msg.from_address,
            from_name=msg.from_name,
            date_sent=msg.date_sent.isoformat(),
            snippet=msg.snippet,
            urgency=urgency,
            action_phrases=action_phrases[:3],  # Limit to top 3
        ))
    
    return decisions
