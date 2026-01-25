"""ARQ tasks for meeting transcription."""

from pathlib import Path

import structlog
from sqlalchemy import select

from jarvis_server.calendar.models import Meeting
from jarvis_server.db.session import AsyncSessionLocal
from jarvis_server.transcription.whisper import get_transcription_service

logger = structlog.get_logger()


async def transcribe_meeting_task(ctx: dict, meeting_id: str) -> dict:
    """
    ARQ task to transcribe meeting audio.

    Args:
        ctx: ARQ context
        meeting_id: ID of meeting to transcribe

    Returns:
        Dict with transcription status and stats
    """
    logger.info("transcription_task_started", meeting_id=meeting_id)

    async with AsyncSessionLocal() as db:
        # Get meeting record
        result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
        meeting = result.scalar_one_or_none()

        if not meeting:
            logger.error("transcription_meeting_not_found", meeting_id=meeting_id)
            return {"status": "error", "reason": "meeting_not_found"}

        if not meeting.audio_path:
            logger.error("transcription_no_audio", meeting_id=meeting_id)
            return {"status": "error", "reason": "no_audio_file"}

        audio_path = Path(meeting.audio_path)
        if not audio_path.exists():
            logger.error(
                "transcription_audio_missing", meeting_id=meeting_id, path=str(audio_path)
            )
            meeting.transcript_status = "failed"
            await db.commit()
            return {"status": "error", "reason": "audio_file_missing"}

        # Update status to processing
        meeting.transcript_status = "processing"
        await db.commit()

        try:
            # Get transcription service and transcribe
            service = get_transcription_service()
            transcription_result = service.transcribe(audio_path)

            # Store transcript
            meeting.transcript = transcription_result.full_text
            meeting.transcript_status = "completed"

            # Store segment data as JSON in a metadata field if we add one
            # For now, just store the full text

            await db.commit()

            logger.info(
                "transcription_task_completed",
                meeting_id=meeting_id,
                language=transcription_result.language,
                duration=transcription_result.duration,
                text_length=len(transcription_result.full_text),
            )

            return {
                "status": "completed",
                "meeting_id": meeting_id,
                "language": transcription_result.language,
                "duration": transcription_result.duration,
                "text_length": len(transcription_result.full_text),
                "segment_count": len(transcription_result.segments),
            }

        except Exception as e:
            logger.exception("transcription_task_failed", meeting_id=meeting_id)
            meeting.transcript_status = "failed"
            await db.commit()
            return {"status": "error", "reason": str(e)}
