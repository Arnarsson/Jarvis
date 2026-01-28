"""Focus Inbox API.

Endpoints:
- GET /api/inbox/triage
- POST /api/inbox/archive-rest
- POST /api/inbox/archive-rest/undo

This is a v1 heuristic implementation intended to support the Command Center "Focus Inbox".
"""

from __future__ import annotations

from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.config import get_settings
from jarvis_server.db.session import get_db
from jarvis_server.email.models import EmailMessage
from jarvis_server.inbox.classifier import classify_focus_inbox_item
from jarvis_server.inbox.undo_store import create_undo_token, pop_undo_ids

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/inbox", tags=["inbox"])


class WhyPriority(BaseModel):
    reasons: list[str]
    confidence: float
    sources: list[dict]


class InboxItem(BaseModel):
    id: str
    type: str
    from_: str | None = None
    subject: str | None = None
    snippet: str | None = None
    received_at: str
    why_priority: WhyPriority
    actions: list[str]

    # Pydantic alias for `from`
    model_config = {"populate_by_name": True}


class TriageStats(BaseModel):
    priority_count: int
    rest_count: int
    noise_ratio: float


class TriageResponse(BaseModel):
    priority: list[InboxItem]
    rest: list[InboxItem]
    stats: TriageStats


class ArchiveRestResponse(BaseModel):
    archived_count: int
    undo_token: str
    undo_expires_at: str


class UndoArchiveResponse(BaseModel):
    restored_count: int


def _vip_set() -> set[str]:
    settings = get_settings()
    return {s.strip().lower() for s in (settings.vip_senders or []) if s.strip()}


def _actions_for_item(_: dict) -> list[str]:
    # v1 fixed actions (frontend can hide/disable).
    return ["reply", "task", "snooze", "archive"]


def _item_payload(
    *,
    msg: EmailMessage,
    previous_contact_at: datetime | None,
    vip_senders: set[str],
) -> tuple[bool, InboxItem]:
    received_at = msg.date_received or msg.date_sent

    cls = classify_focus_inbox_item(
        from_address=msg.from_address,
        subject=msg.subject,
        snippet=msg.snippet,
        body_text=msg.body_text,
        received_at=received_at,
        previous_contact_at=previous_contact_at,
        vip_senders=vip_senders,
    )

    item = InboxItem(
        id=f"email_{msg.id}",
        type="email",
        from_=msg.from_address,
        subject=msg.subject,
        snippet=msg.snippet,
        received_at=received_at.isoformat(),
        why_priority=WhyPriority(**cls["why_priority"]),
        actions=_actions_for_item(cls),
    )

    return bool(cls["is_priority"]), item


async def _load_messages(
    *,
    db: AsyncSession,
    limit: int,
) -> list[EmailMessage]:
    limit = min(max(limit, 1), 500)
    query: Select = (
        select(EmailMessage)
        .where(EmailMessage.is_archived == False)  # noqa: E712
        .order_by(EmailMessage.date_sent.desc())
        .limit(limit)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def _previous_contact_map(
    *,
    db: AsyncSession,
    message_ids: list[str],
) -> dict[str, datetime | None]:
    """Map message_id -> previous contact date for same sender.

    Uses a window function to compute the next older message per sender.
    """

    if not message_ids:
        return {}

    # Use LEAD() over date_sent DESC to obtain the next older message's date.
    prev_dt = func.lead(EmailMessage.date_sent).over(
        partition_by=EmailMessage.from_address,
        order_by=EmailMessage.date_sent.desc(),
    )

    result = await db.execute(
        select(EmailMessage.id, prev_dt.label("prev_contact"))
        .where(EmailMessage.id.in_(message_ids))
    )

    # NOTE: This computes prev_contact within the *selected set* only.
    # For MVP correctness, we compute prev_contact using a second query on all messages for those senders.
    # This avoids window-function partition truncation.
    senders_result = await db.execute(
        select(func.distinct(EmailMessage.from_address)).where(EmailMessage.id.in_(message_ids))
    )
    senders = [s for s in senders_result.scalars().all() if s]

    if not senders:
        return {mid: None for mid in message_ids}

    prev_dt_all = func.lead(EmailMessage.date_sent).over(
        partition_by=EmailMessage.from_address,
        order_by=EmailMessage.date_sent.desc(),
    )

    rows = await db.execute(
        select(EmailMessage.id, prev_dt_all.label("prev_contact"))
        .where(EmailMessage.from_address.in_(senders))
    )

    prev_by_id: dict[str, datetime | None] = {}
    for mid, pdt in rows.all():
        prev_by_id[str(mid)] = pdt

    # Only return for requested ids
    return {mid: prev_by_id.get(mid) for mid in message_ids}


@router.get("/triage", response_model=TriageResponse)
async def triage_inbox(
    limit: int = Query(200, ge=1, le=500, description="Max messages to triage"),
    db: AsyncSession = Depends(get_db),
) -> TriageResponse:
    vip_senders = _vip_set()

    messages = await _load_messages(db=db, limit=limit)
    prev_map = await _previous_contact_map(db=db, message_ids=[m.id for m in messages])

    priority: list[InboxItem] = []
    rest: list[InboxItem] = []

    for m in messages:
        is_pri, item = _item_payload(
            msg=m,
            previous_contact_at=prev_map.get(m.id),
            vip_senders=vip_senders,
        )
        if is_pri:
            priority.append(item)
        else:
            rest.append(item)

    total = len(priority) + len(rest)
    noise_ratio = (len(rest) / total) if total else 0.0

    return TriageResponse(
        priority=priority,
        rest=rest,
        stats=TriageStats(
            priority_count=len(priority),
            rest_count=len(rest),
            noise_ratio=round(noise_ratio, 2),
        ),
    )


@router.post("/archive-rest", response_model=ArchiveRestResponse)
async def archive_rest(
    limit: int = Query(500, ge=1, le=5000, description="Max messages to consider"),
    db: AsyncSession = Depends(get_db),
) -> ArchiveRestResponse:
    """Bulk archive all current "Rest" items.

    Returns an undo token valid for 10 minutes.
    """

    vip_senders = _vip_set()

    messages = await _load_messages(db=db, limit=min(limit, 500))
    prev_map = await _previous_contact_map(db=db, message_ids=[m.id for m in messages])

    rest_ids: list[str] = []
    for m in messages:
        is_pri, _ = _item_payload(
            msg=m,
            previous_contact_at=prev_map.get(m.id),
            vip_senders=vip_senders,
        )
        if not is_pri:
            rest_ids.append(m.id)

    if not rest_ids:
        token, expires_at = create_undo_token(ids=[], ttl_minutes=10)
        return ArchiveRestResponse(
            archived_count=0,
            undo_token=token,
            undo_expires_at=expires_at.isoformat(),
        )

    result = await db.execute(
        select(EmailMessage).where(EmailMessage.id.in_(rest_ids))
    )
    msgs_to_archive = result.scalars().all()

    for m in msgs_to_archive:
        m.is_archived = True

    token, expires_at = create_undo_token(ids=rest_ids, ttl_minutes=10)

    logger.info("inbox_archive_rest", archived_count=len(rest_ids))

    return ArchiveRestResponse(
        archived_count=len(rest_ids),
        undo_token=token,
        undo_expires_at=expires_at.isoformat(),
    )


@router.post("/archive-rest/undo", response_model=UndoArchiveResponse)
async def undo_archive_rest(
    undo_token: str,
    db: AsyncSession = Depends(get_db),
) -> UndoArchiveResponse:
    rec = pop_undo_ids(undo_token)
    if rec is None:
        raise HTTPException(status_code=404, detail="Undo token not found or expired")

    if not rec.ids:
        return UndoArchiveResponse(restored_count=0)

    result = await db.execute(select(EmailMessage).where(EmailMessage.id.in_(rec.ids)))
    msgs = result.scalars().all()

    for m in msgs:
        m.is_archived = False

    logger.info("inbox_undo_archive_rest", restored_count=len(msgs))

    return UndoArchiveResponse(restored_count=len(msgs))
