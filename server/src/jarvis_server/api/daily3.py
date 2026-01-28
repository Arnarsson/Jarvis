"""Daily 3 API — AI-suggested priorities based on calendar, emails, and memory."""

import json
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.db.session import get_db
from jarvis_server.email.models import EmailMessage

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/daily3", tags=["daily3"])


class SuggestedPriority(BaseModel):
    """A single AI-suggested priority."""
    text: str
    source: str  # "calendar", "email", "follow_up"
    urgency: str  # "high", "medium", "low"
    context: str  # why this was suggested
    source_id: str | None = None  # email id, event id, etc.


class Daily3SuggestionsResponse(BaseModel):
    """Response with AI-generated priority suggestions."""
    suggestions: list[SuggestedPriority]
    generated_at: str
    sources_analyzed: dict  # {"emails": N, "events": N, ...}


class Daily3Item(BaseModel):
    """A confirmed daily priority."""
    text: str
    done: bool = False
    source: str | None = None


class Daily3State(BaseModel):
    """Full state of today's Daily 3."""
    date: str
    items: list[Daily3Item]
    suggestions: list[SuggestedPriority] | None = None


# In-memory store (persists across requests, resets on server restart)
# TODO: Move to DB table for persistence
_daily3_store: dict[str, Daily3State] = {}


def _today_key() -> str:
    """Get today's date key in YYYY-MM-DD format (Copenhagen timezone)."""
    from zoneinfo import ZoneInfo
    now = datetime.now(ZoneInfo("Europe/Copenhagen"))
    return now.strftime("%Y-%m-%d")


@router.get("/suggestions", response_model=Daily3SuggestionsResponse)
async def get_suggestions(db: AsyncSession = Depends(get_db)) -> Daily3SuggestionsResponse:
    """Generate AI priority suggestions from calendar events and emails.
    
    Analyzes:
    - Today's calendar events (meetings to prep for)
    - Priority/unread emails needing action
    - Follow-up patterns (emails with action language)
    """
    from zoneinfo import ZoneInfo
    cph = ZoneInfo("Europe/Copenhagen")
    now = datetime.now(cph)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    suggestions: list[SuggestedPriority] = []
    sources_analyzed = {"emails": 0, "events": 0, "decisions": 0}
    
    # 1. Calendar events — meetings today that need prep
    try:
        from jarvis_server.calendar.models import CalendarEvent
        events_q = select(CalendarEvent).where(
            and_(
                CalendarEvent.start_time >= today_start.astimezone(timezone.utc),
                CalendarEvent.start_time < today_end.astimezone(timezone.utc),
            )
        ).order_by(CalendarEvent.start_time)
        result = await db.execute(events_q)
        events = result.scalars().all()
        sources_analyzed["events"] = len(events)
        
        for event in events:
            start_local = event.start_time.astimezone(cph) if event.start_time.tzinfo else event.start_time
            time_str = start_local.strftime("%H:%M")
            attendees = json.loads(event.attendees_json) if event.attendees_json else []
            n_attendees = len(attendees)
            
            # Multi-person meetings are higher priority
            urgency = "high" if n_attendees >= 3 else "medium"
            
            suggestions.append(SuggestedPriority(
                text=f"Prepare for: {event.summary} at {time_str}",
                source="calendar",
                urgency=urgency,
                context=f"{n_attendees} attendees" + (f" @ {event.location}" if event.location else ""),
                source_id=event.id,
            ))
    except Exception as e:
        logger.warning("daily3_calendar_error", error=str(e))
    
    # 2. Priority emails needing action (last 48h)
    action_phrases = [
        "please approve", "need your", "action required", "please confirm",
        "your approval", "sign off", "pending your", "RSVP", "deadline",
        "please review", "waiting for you", "can you", "could you",
        "urgent", "ASAP", "by end of day", "by EOD", "time sensitive",
    ]
    
    try:
        cutoff = now - timedelta(hours=48)
        
        # Get priority + unread emails from last 48h
        emails_q = select(EmailMessage).where(
            and_(
                EmailMessage.date_sent >= cutoff.astimezone(timezone.utc),
                EmailMessage.is_unread == True,  # noqa: E712
            )
        ).order_by(EmailMessage.date_sent.desc()).limit(100)
        
        result = await db.execute(emails_q)
        emails = result.scalars().all()
        sources_analyzed["emails"] = len(emails)
        
        # Score emails by action language
        action_emails = []
        for email in emails:
            searchable = f"{email.subject or ''} {email.snippet or ''} {email.body_text or ''}".lower()
            matches = [phrase for phrase in action_phrases if phrase.lower() in searchable]
            if matches:
                score = len(matches)
                # Boost priority category
                if email.category == "priority":
                    score += 2
                if email.is_important:
                    score += 1
                action_emails.append((email, score, matches))
        
        # Sort by score, take top 5
        action_emails.sort(key=lambda x: x[1], reverse=True)
        sources_analyzed["decisions"] = len(action_emails)
        
        for email, score, matches in action_emails[:5]:
            from_display = email.from_name or email.from_address or "Unknown"
            urgency = "high" if score >= 3 or "urgent" in " ".join(matches) else "medium"
            
            suggestions.append(SuggestedPriority(
                text=f"Respond to: {email.subject or '(no subject)'}",
                source="email",
                urgency=urgency,
                context=f"From {from_display} — {', '.join(matches[:3])}",
                source_id=email.id,
            ))
    except Exception as e:
        logger.warning("daily3_email_error", error=str(e))
    
    # 3. Follow-up detection — emails where someone said they'd do something
    follow_up_phrases = [
        "i'll send you", "will get back", "let me check", "i'll follow up",
        "will share", "i'll prepare", "let's schedule", "will set up",
    ]
    
    try:
        # Check last 7 days for follow-ups
        week_ago = now - timedelta(days=7)
        fu_q = select(EmailMessage).where(
            and_(
                EmailMessage.date_sent >= week_ago.astimezone(timezone.utc),
                EmailMessage.date_sent < cutoff.astimezone(timezone.utc),  # Older than 48h = might be overdue
            )
        ).limit(200)
        
        result = await db.execute(fu_q)
        older_emails = result.scalars().all()
        
        for email in older_emails:
            searchable = f"{email.snippet or ''} {email.body_text or ''}".lower()
            fu_matches = [p for p in follow_up_phrases if p in searchable]
            if fu_matches:
                from_display = email.from_name or email.from_address or "Unknown"
                days_ago = (now - email.date_sent.replace(tzinfo=cph if not email.date_sent.tzinfo else email.date_sent.tzinfo)).days
                
                suggestions.append(SuggestedPriority(
                    text=f"Follow up with {from_display}: {email.subject or '(no subject)'}",
                    source="follow_up",
                    urgency="low" if days_ago < 5 else "medium",
                    context=f"{days_ago} days ago — they said: '{fu_matches[0]}'",
                    source_id=email.id,
                ))
    except Exception as e:
        logger.warning("daily3_followup_error", error=str(e))
    
    # Sort: high urgency first, then calendar, then email, then follow-ups
    urgency_order = {"high": 0, "medium": 1, "low": 2}
    source_order = {"calendar": 0, "email": 1, "follow_up": 2}
    suggestions.sort(key=lambda s: (urgency_order.get(s.urgency, 9), source_order.get(s.source, 9)))
    
    # Cap at 9 suggestions (user picks 3)
    suggestions = suggestions[:9]
    
    return Daily3SuggestionsResponse(
        suggestions=suggestions,
        generated_at=now.isoformat(),
        sources_analyzed=sources_analyzed,
    )


@router.get("/today", response_model=Daily3State | None)
async def get_today() -> Daily3State | None:
    """Get today's confirmed Daily 3 items."""
    key = _today_key()
    return _daily3_store.get(key)


@router.post("/today", response_model=Daily3State)
async def set_today(items: list[Daily3Item]) -> Daily3State:
    """Set or update today's Daily 3 items."""
    key = _today_key()
    state = Daily3State(date=key, items=items[:3])
    _daily3_store[key] = state
    logger.info("daily3_set", date=key, items=[i.text for i in items[:3]])
    return state


@router.patch("/today/{index}/toggle")
async def toggle_item(index: int) -> Daily3State:
    """Toggle completion of a Daily 3 item."""
    key = _today_key()
    state = _daily3_store.get(key)
    if not state or index < 0 or index >= len(state.items):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Item not found")
    
    state.items[index].done = not state.items[index].done
    logger.info("daily3_toggle", date=key, index=index, done=state.items[index].done)
    return state
