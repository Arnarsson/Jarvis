"""Resume API - infer the last active project/thread for instant context recovery."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.api.captures import get_storage
from jarvis_server.db.models import Capture, ConversationRecord
from jarvis_server.db.session import get_db
from jarvis_server.services.resume_engine import (
    CaptureSignal,
    append_feedback,
    build_resume_from_captures,
    infer_last_decision_and_next_action,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/resume", tags=["resume"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ResumeProject(BaseModel):
    name: str | None = None
    confidence: float = 0.0
    last_active: str | None = None
    duration_today: str | None = None


class OpenFile(BaseModel):
    name: str
    path: str


class RecentCommit(BaseModel):
    message: str
    time: str


class ResumeContext(BaseModel):
    last_decision: str | None = None
    next_action: str | None = None
    open_files: list[OpenFile] = Field(default_factory=list)
    recent_commits: list[RecentCommit] = Field(default_factory=list)


class ResumeAction(BaseModel):
    label: str
    action: str


class WhyPayload(BaseModel):
    reasons: list[str]
    confidence: float
    sources: list[dict]


class ResumeResponse(BaseModel):
    project: ResumeProject
    context: ResumeContext
    actions: list[ResumeAction]
    why: WhyPayload


class ResumeFeedbackRequest(BaseModel):
    correct: bool
    actual_project: str | None = None
    suggested_project: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=ResumeResponse)
async def get_resume(
    hours: int = 4,
    db: AsyncSession = Depends(get_db),
) -> ResumeResponse:
    """Infer the last active project based on recent captures.

    MVP implementation that works even with basic OCR.
    """

    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=hours)

    # Pull recent captures (only those with OCR text)
    result = await db.execute(
        select(Capture)
        .where(Capture.timestamp >= since)
        .where(Capture.ocr_text.is_not(None))
        .order_by(Capture.timestamp.asc())
        .limit(1000)
    )
    captures = list(result.scalars().all())

    signals = [
        CaptureSignal(id=c.id, timestamp=c.timestamp, ocr_text=c.ocr_text or "")
        for c in captures
        if c.ocr_text
    ]

    stats, why = build_resume_from_captures(signals, now=now)

    if not stats:
        return ResumeResponse(
            project=ResumeProject(name=None, confidence=0.0, last_active=None, duration_today=None),
            context=ResumeContext(),
            actions=[
                ResumeAction(label="View Brief", action="show_brief"),
                ResumeAction(label="Wrong Project", action="choose_other"),
            ],
            why=WhyPayload(**why),
        )

    # Find recent conversations that mention the project for decision/next action heuristics
    conv_result = await db.execute(
        select(ConversationRecord)
        .where(ConversationRecord.full_text.ilike(f"%{stats.name}%"))
        .order_by(ConversationRecord.conversation_date.desc().nullslast())
        .limit(5)
    )
    convs = list(conv_result.scalars().all())

    fallback_commit = None
    if stats.recent_commits:
        fallback_commit = stats.recent_commits[0]["message"]

    last_decision, next_action = infer_last_decision_and_next_action(
        project_name=stats.name,
        conversation_texts=[c.full_text for c in convs],
        fallback_commit_message=fallback_commit,
    )

    duration_today = None
    if stats.duration_seconds is not None:
        # stats.duration_seconds is seconds for today if possible
        from jarvis_server.services.resume_engine import _human_duration

        duration_today = _human_duration(stats.duration_seconds)

    recent_commits = []
    for c in stats.recent_commits or []:
        recent_commits.append(RecentCommit(**c))

    return ResumeResponse(
        project=ResumeProject(
            name=stats.name,
            confidence=float(why.get("confidence", 0.0)),
            last_active=stats.last_active.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            duration_today=duration_today,
        ),
        context=ResumeContext(
            last_decision=last_decision,
            next_action=next_action,
            open_files=[OpenFile(**f) for f in stats.open_files],
            recent_commits=recent_commits,
        ),
        actions=[
            ResumeAction(label="Resume Workspace", action="open_files"),
            ResumeAction(label="View Brief", action="show_brief"),
            ResumeAction(label="Wrong Project", action="choose_other"),
        ],
        why=WhyPayload(**why),
    )


@router.post("/feedback")
async def post_resume_feedback(
    request: ResumeFeedbackRequest,
    storage=Depends(get_storage),
) -> dict:
    """Store feedback for resume suggestions.

    Stored as JSONL in the capture storage directory (cheap + append-only).
    """

    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "correct": request.correct,
        "actual_project": request.actual_project,
        "suggested_project": request.suggested_project,
    }

    append_feedback(storage.base_path, payload)

    logger.info("resume_feedback_recorded", correct=request.correct)

    return {"status": "ok"}
