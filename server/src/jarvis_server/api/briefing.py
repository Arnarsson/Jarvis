"""Morning Briefing API - comprehensive synthesis for voice delivery.

Generates a conversational morning briefing aggregating calendar, email,
patterns, promises, and daily priorities.
"""

import structlog
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.db.session import get_db
from jarvis_server.db.models import DetectedPattern, Promise
from jarvis_server.email.models import EmailMessage
from jarvis_server.calendar.models import CalendarEvent

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v2/briefing", tags=["briefing"])


# Response Models
class CalendarItem(BaseModel):
    """Calendar event for briefing."""
    summary: str
    start_time: str
    end_time: str
    location: str | None = None
    attendees: list[str] = []


class EmailHighlight(BaseModel):
    """Priority email highlight."""
    subject: str
    from_name: str
    from_address: str
    snippet: str
    received: str
    priority: str


class UnfinishedItem(BaseModel):
    """Unfinished business from patterns."""
    topic: str
    description: str
    last_seen: str
    suggested_action: str


class FollowUpItem(BaseModel):
    """Follow-up or promise due."""
    text: str
    due_by: str | None
    days_overdue: int | None


class PatternAlert(BaseModel):
    """Notable pattern requiring attention."""
    pattern_type: str
    key: str
    description: str
    suggested_action: str


class Daily3Suggestion(BaseModel):
    """Suggested priority for today."""
    priority: str
    rationale: str


class OvernightActivity(BaseModel):
    """Overnight agent/computer activity."""
    hour: int
    summary: str
    apps: list[str]
    topics: list[str]


class LinearTask(BaseModel):
    """Linear task for briefing."""
    identifier: str
    title: str
    state: str
    priority: int
    priority_label: str
    due_date: str | None


class MorningBriefingResponse(BaseModel):
    """Complete morning briefing."""
    text: str
    sections: dict
    generated_at: str


def format_time(dt: datetime) -> str:
    """Format time for voice reading (e.g., '9:30 AM')."""
    return dt.strftime("%I:%M %p").lstrip("0").replace(" 0", " ")


def format_date(dt: datetime) -> str:
    """Format date for voice reading (e.g., 'Monday, January 27th')."""
    day = dt.strftime("%A, %B ")
    day_num = dt.day
    suffix = "th" if 11 <= day_num <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day_num % 10, "th")
    return f"{day}{day_num}{suffix}"


async def get_calendar_events(db: AsyncSession, today_start: datetime, today_end: datetime) -> list[CalendarItem]:
    """Fetch today's calendar events."""
    result = await db.execute(
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
    events = result.scalars().all()
    
    calendar_items = []
    for event in events:
        import json
        attendees = []
        if event.attendees_json:
            try:
                att_list = json.loads(event.attendees_json)
                attendees = [a.get("name") or a.get("email", "Unknown") for a in att_list if isinstance(a, dict)]
            except:
                pass
        
        calendar_items.append(CalendarItem(
            summary=event.summary or "Untitled Event",
            start_time=event.start_time.isoformat(),
            end_time=event.end_time.isoformat() if event.end_time else "",
            location=event.location,
            attendees=attendees,
        ))
    
    return calendar_items


async def get_email_highlights(db: AsyncSession) -> list[EmailHighlight]:
    """Fetch priority unread emails from last 24h."""
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    
    result = await db.execute(
        select(EmailMessage)
        .where(
            and_(
                EmailMessage.date_sent >= yesterday,
                EmailMessage.is_unread == True,
            )
        )
        .order_by(EmailMessage.date_sent.desc())
        .limit(5)
    )
    emails = result.scalars().all()
    
    highlights = []
    for email in emails:
        snippet = email.snippet if email.snippet else (email.body_text[:150] if email.body_text else "")
        snippet = snippet.replace("\n", " ").strip()
        
        highlights.append(EmailHighlight(
            subject=email.subject or "No Subject",
            from_name=email.from_name or "Unknown",
            from_address=email.from_address or "",
            snippet=snippet,
            received=email.date_sent.isoformat(),
            priority="normal",
        ))
    
    return highlights


async def get_unfinished_business(db: AsyncSession) -> list[UnfinishedItem]:
    """Fetch unfinished business patterns."""
    result = await db.execute(
        select(DetectedPattern)
        .where(
            and_(
                DetectedPattern.pattern_type == "unfinished_business",
                DetectedPattern.status == "active"
            )
        )
        .order_by(DetectedPattern.frequency.desc())
        .limit(3)
    )
    patterns = result.scalars().all()
    
    items = []
    for p in patterns:
        items.append(UnfinishedItem(
            topic=p.pattern_key,
            description=p.description,
            last_seen=p.last_seen.isoformat(),
            suggested_action=p.suggested_action or "Review status",
        ))
    
    return items


async def get_follow_ups_due(db: AsyncSession) -> list[FollowUpItem]:
    """Fetch promises/follow-ups that are due or overdue."""
    now = datetime.now(timezone.utc)
    
    result = await db.execute(
        select(Promise)
        .where(
            and_(
                Promise.status == "pending",
                or_(
                    Promise.due_by <= now,
                    Promise.due_by.is_(None)
                )
            )
        )
        .order_by(Promise.detected_at.desc())
        .limit(5)
    )
    promises = result.scalars().all()
    
    items = []
    for p in promises:
        days_overdue = None
        if p.due_by:
            delta = now - p.due_by
            days_overdue = delta.days if delta.days > 0 else None
        
        items.append(FollowUpItem(
            text=p.text,
            due_by=p.due_by.isoformat() if p.due_by else None,
            days_overdue=days_overdue,
        ))
    
    return items


async def get_pattern_alerts(db: AsyncSession) -> list[PatternAlert]:
    """Fetch notable patterns requiring attention."""
    result = await db.execute(
        select(DetectedPattern)
        .where(
            and_(
                DetectedPattern.pattern_type.in_(["stale_person", "broken_promise", "stale_project"]),
                DetectedPattern.status == "active"
            )
        )
        .order_by(DetectedPattern.last_seen.asc())
        .limit(5)
    )
    patterns = result.scalars().all()
    
    alerts = []
    for p in patterns:
        alerts.append(PatternAlert(
            pattern_type=p.pattern_type,
            key=p.pattern_key,
            description=p.description,
            suggested_action=p.suggested_action or "Review",
        ))
    
    return alerts


async def get_overnight_activity(db: AsyncSession) -> list[OvernightActivity]:
    """Fetch overnight computer activity (10 PM - 8 AM)."""
    from jarvis_server.db.models import Capture
    
    now = datetime.now(timezone.utc)
    
    # Define overnight period: yesterday 10 PM to today 8 AM
    today_8am = now.replace(hour=8, minute=0, second=0, microsecond=0)
    yesterday_10pm = (now - timedelta(days=1)).replace(hour=22, minute=0, second=0, microsecond=0)
    
    # If it's before 8 AM, we're still in the overnight period
    if now.hour < 8:
        yesterday_10pm = (now - timedelta(days=1)).replace(hour=22, minute=0, second=0, microsecond=0)
        today_8am = now.replace(hour=8, minute=0, second=0, microsecond=0)
    else:
        # After 8 AM, show last night's activity
        yesterday_10pm = (now - timedelta(days=1)).replace(hour=22, minute=0, second=0, microsecond=0)
        today_8am = now.replace(hour=8, minute=0, second=0, microsecond=0)
    
    # Fetch captures from overnight period with OCR text
    result = await db.execute(
        select(Capture)
        .where(
            and_(
                Capture.timestamp >= yesterday_10pm,
                Capture.timestamp < today_8am,
                Capture.ocr_text.isnot(None),
            )
        )
        .order_by(Capture.timestamp)
    )
    captures = list(result.scalars().all())
    
    if not captures:
        return []
    
    # Import activity analysis functions
    from jarvis_server.api.activity import detect_apps, extract_topics, clean_ocr_text, summarize_hour
    
    # Group by hour
    from collections import defaultdict
    by_hour = defaultdict(list)
    for c in captures:
        hour = c.timestamp.hour
        by_hour[hour].append(c)
    
    # Build hour summaries
    activities = []
    for hour in sorted(by_hour.keys()):
        hour_captures = by_hour[hour]
        all_text = []
        for c in hour_captures:
            cleaned = clean_ocr_text(c.ocr_text or "")
            if cleaned:
                all_text.append(cleaned)
        
        combined = "\n---\n".join(all_text)
        apps = detect_apps(combined)
        topics = extract_topics(combined)
        summary = summarize_hour(all_text, apps, topics)
        
        activities.append(OvernightActivity(
            hour=hour,
            summary=summary,
            apps=apps,
            topics=topics,
        ))
    
    return activities


async def get_linear_tasks() -> list[LinearTask]:
    """Fetch Linear tasks that are in progress or high priority."""
    import os
    import httpx
    from pathlib import Path
    
    # Get Linear API key
    api_key = os.environ.get("LINEAR_API_KEY")
    if not api_key:
        for path in [Path.home() / ".linear_api_key", Path("/data/.linear_api_key")]:
            if path.exists():
                api_key = path.read_text().strip()
                break
    
    if not api_key:
        logger.warning("linear_api_key_not_found")
        return []
    
    # Fetch tasks from Linear
    query = """
    query($teamId: String!, $first: Int!, $stateTypes: [String!]) {
        team(id: $teamId) {
            issues(
                first: $first,
                filter: { state: { type: { in: $stateTypes } } },
                orderBy: updatedAt
            ) {
                nodes {
                    identifier
                    title
                    state { name }
                    priority
                    priorityLabel
                    dueDate
                }
            }
        }
    }
    """
    
    variables = {
        "teamId": "b4f3046f-b603-43fb-94b5-5f17dd9396e0",
        "first": 10,
        "stateTypes": ["started", "unstarted"],
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.linear.app/graphql",
                json={"query": query, "variables": variables},
                headers={
                    "Content-Type": "application/json",
                    "Authorization": api_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        
        issues = data.get("data", {}).get("team", {}).get("issues", {}).get("nodes", [])
        
        tasks = []
        for issue in issues:
            # Only include high priority tasks (priority 1-2) or in-progress tasks
            if issue["priority"] <= 2 or issue["state"]["name"] == "In Progress":
                tasks.append(LinearTask(
                    identifier=issue["identifier"],
                    title=issue["title"],
                    state=issue["state"]["name"],
                    priority=issue["priority"],
                    priority_label=issue["priorityLabel"],
                    due_date=issue.get("dueDate"),
                ))
        
        return tasks
    except Exception as e:
        logger.error("linear_fetch_failed", error=str(e))
        return []


def generate_briefing_text(
    date_str: str,
    calendar: list[CalendarItem],
    emails: list[EmailHighlight],
    unfinished: list[UnfinishedItem],
    follow_ups: list[FollowUpItem],
    patterns: list[PatternAlert],
    overnight: list[OvernightActivity],
    linear_tasks: list[LinearTask],
) -> str:
    """Generate conversational briefing text for voice reading."""
    lines = []
    
    # Greeting
    lines.append(f"Good morning Sven. Here's your briefing for {date_str}.")
    lines.append("")
    
    # Overnight activity
    if overnight:
        lines.append(f"Overnight activity detected in {len(overnight)} hour{'s' if len(overnight) > 1 else ''}:")
        for activity in overnight[:3]:
            hour_str = f"{activity.hour:02d}:00"
            lines.append(f"- {hour_str}: {activity.summary}")
        lines.append("")
    
    # Calendar
    if calendar:
        lines.append(f"You have {len(calendar)} event{'s' if len(calendar) > 1 else ''} on your calendar today.")
        for i, event in enumerate(calendar, 1):
            start = datetime.fromisoformat(event.start_time)
            time_str = format_time(start)
            attendees_str = ""
            if event.attendees:
                if len(event.attendees) == 1:
                    attendees_str = f" with {event.attendees[0]}"
                elif len(event.attendees) == 2:
                    attendees_str = f" with {event.attendees[0]} and {event.attendees[1]}"
                else:
                    attendees_str = f" with {len(event.attendees)} attendees"
            
            lines.append(f"{i}. {time_str}: {event.summary}{attendees_str}")
    else:
        lines.append("You have no scheduled events today.")
    
    lines.append("")
    
    # Linear tasks
    if linear_tasks:
        in_progress = [t for t in linear_tasks if t.state == "In Progress"]
        high_priority = [t for t in linear_tasks if t.priority <= 2 and t.state != "In Progress"]
        
        if in_progress:
            lines.append(f"You have {len(in_progress)} task{'s' if len(in_progress) > 1 else ''} in progress:")
            for i, task in enumerate(in_progress[:3], 1):
                lines.append(f"{i}. {task.identifier}: {task.title}")
        
        if high_priority:
            if in_progress:
                lines.append("")
            lines.append(f"{len(high_priority)} high-priority task{'s' if len(high_priority) > 1 else ''} waiting:")
            for i, task in enumerate(high_priority[:3], 1):
                lines.append(f"{i}. {task.identifier}: {task.title}")
        
        lines.append("")
    
    # Email highlights
    if emails:
        lines.append(f"You have {len(emails)} priority email{'s' if len(emails) > 1 else ''} from the last 24 hours.")
        for i, email in enumerate(emails[:3], 1):
            lines.append(f"{i}. {email.from_name}: {email.subject}")
    else:
        lines.append("No priority emails in the last 24 hours.")
    
    lines.append("")
    
    # Unfinished business
    if unfinished:
        lines.append(f"There are {len(unfinished)} unfinished topics requiring attention:")
        for i, item in enumerate(unfinished[:3], 1):
            lines.append(f"{i}. {item.topic} - {item.suggested_action}")
    
    # Follow-ups
    if follow_ups:
        lines.append("")
        overdue = [f for f in follow_ups if f.days_overdue and f.days_overdue > 0]
        if overdue:
            lines.append(f"You have {len(overdue)} overdue follow-up{'s' if len(overdue) > 1 else ''}:")
            for i, item in enumerate(overdue[:3], 1):
                days_str = f"{item.days_overdue} day{'s' if item.days_overdue > 1 else ''}"
                lines.append(f"{i}. {item.text} - overdue by {days_str}")
    
    # Pattern alerts
    if patterns:
        stale_people = [p for p in patterns if p.pattern_type == "stale_person"]
        if stale_people:
            lines.append("")
            lines.append(f"You have {len(stale_people)} stale contact{'s' if len(stale_people) > 1 else ''} to reconnect with:")
            for i, alert in enumerate(stale_people[:2], 1):
                lines.append(f"{i}. {alert.key}")
    
    lines.append("")
    lines.append("That's your briefing. Have a productive day.")
    
    return "\n".join(lines)


@router.get("/morning", response_model=MorningBriefingResponse)
async def morning_briefing(
    db: AsyncSession = Depends(get_db),
) -> MorningBriefingResponse:
    """Generate comprehensive morning briefing for voice delivery.
    
    Aggregates:
    - Today's calendar events
    - Priority unread emails (24h)
    - Unfinished business patterns
    - Follow-ups/promises due
    - Notable pattern alerts
    
    Text is formatted conversationally for text-to-speech.
    """
    try:
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        # Fetch all sections
        calendar = await get_calendar_events(db, today_start, today_end)
        emails = await get_email_highlights(db)
        unfinished = await get_unfinished_business(db)
        follow_ups = await get_follow_ups_due(db)
        patterns = await get_pattern_alerts(db)
        overnight = await get_overnight_activity(db)
        linear_tasks = await get_linear_tasks()
        
        # Generate text
        date_str = format_date(now)
        briefing_text = generate_briefing_text(
            date_str,
            calendar,
            emails,
            unfinished,
            follow_ups,
            patterns,
            overnight,
            linear_tasks,
        )
        
        logger.info(
            "morning_briefing_generated",
            calendar_events=len(calendar),
            emails=len(emails),
            unfinished=len(unfinished),
            follow_ups=len(follow_ups),
            patterns=len(patterns),
            overnight_hours=len(overnight),
            linear_tasks=len(linear_tasks),
        )
        
        return MorningBriefingResponse(
            text=briefing_text,
            sections={
                "calendar": [c.model_dump() for c in calendar],
                "email_highlights": [e.model_dump() for e in emails],
                "unfinished_business": [u.model_dump() for u in unfinished],
                "follow_ups_due": [f.model_dump() for f in follow_ups],
                "pattern_alerts": [p.model_dump() for p in patterns],
                "overnight_activity": [o.model_dump() for o in overnight],
                "linear_tasks": [t.model_dump() for t in linear_tasks],
                "daily3_suggestions": [],  # Placeholder for future integration
            },
            generated_at=now.isoformat(),
        )
        
    except Exception as e:
        logger.error("morning_briefing_failed", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate morning briefing")
