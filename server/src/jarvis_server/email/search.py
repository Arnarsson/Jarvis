"""Search emails for meeting context."""

from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.email.models import EmailMessage
from jarvis_server.search.hybrid import hybrid_search
from jarvis_server.search.schemas import SearchRequest

logger = structlog.get_logger()


async def search_emails_for_meeting(
    db: AsyncSession,
    attendee_emails: list[str],
    meeting_topic: str,
    lookback_days: int = 30,
    max_results: int = 5,
) -> list[EmailMessage]:
    """Search for emails relevant to a meeting.

    Finds emails by:
    1. From/To matching attendee email addresses
    2. Subject/body matching meeting topic (semantic search)

    Args:
        db: Database session
        attendee_emails: List of attendee email addresses to search for
        meeting_topic: Meeting title/topic for semantic search
        lookback_days: How far back to search (default 30 days)
        max_results: Maximum number of emails to return

    Returns:
        List of relevant EmailMessage objects, sorted by date descending
    """
    results: list[EmailMessage] = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    # 1. Search by attendee addresses
    if attendee_emails:
        # Build OR conditions for each attendee email
        addr_conditions = []
        for addr in attendee_emails[:10]:  # Limit to avoid huge queries
            addr_conditions.append(EmailMessage.from_address.ilike(f"%{addr}%"))
            addr_conditions.append(EmailMessage.to_addresses.ilike(f"%{addr}%"))

        if addr_conditions:
            query = (
                select(EmailMessage)
                .where(EmailMessage.date_sent >= cutoff, or_(*addr_conditions))
                .order_by(EmailMessage.date_sent.desc())
                .limit(max_results)
            )

            result = await db.execute(query)
            results.extend(result.scalars().all())
            logger.debug(
                "email_search_by_attendee",
                attendees=len(attendee_emails),
                found=len(results),
            )

    # 2. Semantic search by topic if we have one
    if meeting_topic and len(meeting_topic) > 3:
        try:
            request = SearchRequest(
                query=meeting_topic,
                sources=["email"],
                limit=max_results,
                start_date=cutoff,
            )
            search_results = hybrid_search(request)

            # Fetch full email records for results
            for sr in search_results:
                if sr.source == "email" and sr.id:
                    email = await db.get(EmailMessage, sr.id)
                    if email and email not in results:
                        results.append(email)

            logger.debug(
                "email_search_by_topic",
                topic=meeting_topic[:50],
                found=len(search_results),
            )
        except Exception as e:
            logger.warning("email_semantic_search_failed", error=str(e))

    # Deduplicate and sort by date
    seen_ids: set[str] = set()
    unique_results: list[EmailMessage] = []
    for email in results:
        if email.id not in seen_ids:
            seen_ids.add(email.id)
            unique_results.append(email)

    unique_results.sort(key=lambda e: e.date_sent or datetime.min, reverse=True)
    return unique_results[:max_results]


def format_email_context(emails: list[EmailMessage]) -> str:
    """Format emails for brief context section.

    Args:
        emails: List of EmailMessage objects

    Returns:
        Formatted string for inclusion in meeting brief prompt
    """
    if not emails:
        return "No relevant recent emails found."

    lines = ["Recent related emails:"]
    for email in emails:
        date_str = email.date_sent.strftime("%m/%d") if email.date_sent else "?"
        from_str = email.from_name or email.from_address or "Unknown"
        subject = email.subject or "No subject"
        snippet = (email.snippet or "")[:100]

        lines.append(f"- [{date_str}] {from_str}: {subject}")
        if snippet:
            lines.append(f'  "{snippet}..."')

    return "\n".join(lines)
