"""ARQ tasks for meeting summarization."""

import json

import structlog
from sqlalchemy import select

from jarvis_server.calendar.models import CalendarEvent, Meeting
from jarvis_server.db.session import AsyncSessionLocal
from jarvis_server.meetings.summaries import generate_meeting_summary

logger = structlog.get_logger()


async def summarize_meeting_task(ctx: dict, meeting_id: str) -> dict:
    """
    ARQ task to summarize a transcribed meeting.

    Args:
        ctx: ARQ context
        meeting_id: ID of meeting to summarize

    Returns:
        Dict with summarization status
    """
    logger.info("summarization_task_started", meeting_id=meeting_id)

    async with AsyncSessionLocal() as db:
        # Get meeting record
        result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
        meeting = result.scalar_one_or_none()

        if not meeting:
            logger.error("summarization_meeting_not_found", meeting_id=meeting_id)
            return {"status": "error", "reason": "meeting_not_found"}

        if not meeting.transcript:
            logger.error("summarization_no_transcript", meeting_id=meeting_id)
            return {"status": "error", "reason": "no_transcript"}

        # Get meeting title from calendar event if linked
        meeting_title = None
        if meeting.calendar_event_id:
            result = await db.execute(
                select(CalendarEvent).where(CalendarEvent.id == meeting.calendar_event_id)
            )
            event = result.scalar_one_or_none()
            if event:
                meeting_title = event.summary

        try:
            # Generate summary
            summary = await generate_meeting_summary(
                transcript=meeting.transcript, meeting_title=meeting_title
            )

            # Store in meeting record
            meeting.summary = summary.summary
            meeting.action_items_json = json.dumps(
                [
                    {
                        "task": item.task,
                        "owner": item.owner,
                        "due_date": item.due_date,
                        "priority": item.priority,
                    }
                    for item in summary.action_items
                ]
            )

            await db.commit()

            logger.info(
                "summarization_task_completed",
                meeting_id=meeting_id,
                action_items=len(summary.action_items),
                decisions=len(summary.key_decisions),
            )

            return {
                "status": "completed",
                "meeting_id": meeting_id,
                "summary_length": len(summary.summary),
                "action_item_count": len(summary.action_items),
                "key_decisions": summary.key_decisions,
                "follow_ups": summary.follow_ups,
            }

        except Exception as e:
            logger.exception("summarization_task_failed", meeting_id=meeting_id)
            return {"status": "error", "reason": str(e)}
