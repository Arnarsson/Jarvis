"""Pre-meeting brief generation using memory search and LLM."""

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import anthropic
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.calendar.models import CalendarEvent, Meeting
from jarvis_server.search.hybrid import hybrid_search
from jarvis_server.search.schemas import SearchRequest

logger = structlog.get_logger()

# LLM client - lazy init
_client: Optional[anthropic.AsyncAnthropic] = None


def get_llm_client() -> anthropic.AsyncAnthropic:
    """Get or create Anthropic client."""
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        _client = anthropic.AsyncAnthropic(api_key=api_key)
    return _client


BRIEF_PROMPT = """You are preparing a pre-meeting brief for someone about to join a meeting.

Meeting Details:
- Title: {title}
- Time: {time}
- Attendees: {attendees}
- Description: {description}

## Context from Memory
{context}

## Email Highlights
{email_context}

Generate a concise pre-meeting brief covering:
1. **Key Context**: What's this meeting about based on the title and any related past discussions?
2. **Attendee Notes**: Any relevant recent interactions with the attendees (if found in context).
3. **Email Threads**: Relevant recent email exchanges with attendees or about the topic.
4. **Open Items**: Any pending questions, action items, or follow-ups related to this topic.
5. **Suggested Preparation**: Quick recommendations for the meeting.

Keep the brief focused and actionable. If there's limited context available, acknowledge that and focus on what can be inferred from the meeting details.

Format with markdown headers and bullet points for easy scanning."""


async def gather_meeting_context(
    event: CalendarEvent,
    db: AsyncSession,
    max_results: int = 10
) -> tuple[str, str]:
    """Search memory and email for context relevant to the meeting.

    Uses hybrid search to find relevant captures based on meeting
    title and attendee information, and searches for relevant emails
    from/to attendees.

    Args:
        event: The calendar event
        db: Database session for email queries
        max_results: Maximum memory results to return

    Returns:
        Tuple of (memory_context, email_context)
    """
    search_terms = []
    attendee_emails: list[str] = []

    # Add meeting title words (skip common words)
    if event.summary:
        words = event.summary.split()
        # Filter out short/common words
        significant = [w for w in words if len(w) > 3 and w.lower() not in
                       {'meeting', 'call', 'sync', 'with', 'about', 'the', 'and', 'for'}]
        search_terms.extend(significant[:3])

    # Add attendee names/emails
    if event.attendees_json:
        try:
            attendees = json.loads(event.attendees_json)
            for attendee in attendees[:10]:
                # Extract email address
                email_addr = attendee.get('email')
                if email_addr:
                    attendee_emails.append(email_addr)
                # Extract name or email prefix for memory search
                name = attendee.get('displayName') or email_addr.split('@')[0] if email_addr else None
                if name and len(name) > 2:
                    search_terms.append(name)
        except (json.JSONDecodeError, TypeError):
            pass

    # Gather memory context
    memory_context = "No specific context found - this appears to be a new topic."
    if search_terms:
        all_results = []
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

        for term in search_terms[:5]:  # Limit queries
            try:
                request = SearchRequest(
                    query=term,
                    limit=5,
                    start_date=thirty_days_ago
                )
                results = hybrid_search(request)
                all_results.extend(results)
            except Exception as e:
                logger.warning("brief_search_failed", term=term, error=str(e))

        # Deduplicate by ID
        seen_ids: set[str] = set()
        unique_results = []
        for r in all_results:
            if r.id not in seen_ids:
                seen_ids.add(r.id)
                unique_results.append(r)

        # Format top results
        if unique_results:
            context_parts = []
            for i, result in enumerate(unique_results[:max_results], 1):
                source = result.source
                date_str = result.timestamp.strftime('%Y-%m-%d') if result.timestamp else 'Unknown date'
                text = result.text_preview
                # Truncate long text
                if len(text) > 500:
                    text = text[:500] + "..."
                context_parts.append(f"{i}. [{source}] {date_str}\n   {text}")
            memory_context = "\n\n".join(context_parts)
        else:
            memory_context = "No relevant context found in memory for this meeting."

    # Gather email context
    from jarvis_server.email.search import format_email_context, search_emails_for_meeting

    email_results = await search_emails_for_meeting(
        db=db,
        attendee_emails=attendee_emails,
        meeting_topic=event.summary or "",
        lookback_days=30,
        max_results=5,
    )
    email_context = format_email_context(email_results)

    return memory_context, email_context


async def generate_pre_meeting_brief(
    event: CalendarEvent,
    db: AsyncSession
) -> str:
    """Generate a pre-meeting brief for a calendar event.

    Args:
        event: The calendar event to generate brief for
        db: Database session for email queries

    Returns:
        Generated brief text
    """
    logger.info("generating_brief", event_id=event.id, summary=event.summary)

    # Gather context from memory and email
    memory_context, email_context = await gather_meeting_context(event, db)

    # Format attendees
    attendees_list = []
    if event.attendees_json:
        try:
            attendees = json.loads(event.attendees_json)
            for a in attendees[:10]:
                name = a.get('displayName') or a.get('email', 'Unknown')
                attendees_list.append(name)
        except (json.JSONDecodeError, TypeError):
            pass
    attendees_str = ", ".join(attendees_list) if attendees_list else "No attendees listed"

    # Build prompt
    prompt = BRIEF_PROMPT.format(
        title=event.summary or "Untitled Meeting",
        time=event.start_time.strftime('%Y-%m-%d %H:%M') if event.start_time else "Unknown",
        attendees=attendees_str,
        description=event.description or "No description provided",
        context=memory_context,
        email_context=email_context
    )

    # Call LLM
    try:
        client = get_llm_client()
        message = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        brief = message.content[0].text
        logger.info("brief_generated", event_id=event.id, length=len(brief))
        return brief

    except Exception as e:
        logger.error("brief_generation_failed", event_id=event.id, error=str(e))
        raise


async def get_or_generate_brief(
    event_id: str,
    db: AsyncSession,
    force_regenerate: bool = False
) -> tuple[str, bool]:
    """Get cached brief or generate new one.

    Args:
        event_id: The calendar event ID
        db: Database session
        force_regenerate: If True, regenerate even if cached

    Returns:
        Tuple of (brief_text, was_generated)
    """
    # Find event
    result = await db.execute(
        select(CalendarEvent).where(CalendarEvent.id == event_id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise ValueError(f"Calendar event not found: {event_id}")

    # Check for existing meeting with brief
    if not force_regenerate:
        result = await db.execute(
            select(Meeting).where(Meeting.calendar_event_id == event_id)
        )
        meeting = result.scalar_one_or_none()
        if meeting and meeting.brief:
            return meeting.brief, False

    # Generate new brief
    brief = await generate_pre_meeting_brief(event, db)

    # Store in meeting record (create if needed)
    result = await db.execute(
        select(Meeting).where(Meeting.calendar_event_id == event_id)
    )
    meeting = result.scalar_one_or_none()

    if meeting:
        meeting.brief = brief
        meeting.brief_generated_at = datetime.now(timezone.utc)
    else:
        meeting = Meeting(
            calendar_event_id=event_id,
            detected_at=datetime.now(timezone.utc),
            brief=brief,
            brief_generated_at=datetime.now(timezone.utc)
        )
        db.add(meeting)

    await db.commit()

    return brief, True
