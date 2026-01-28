"""Today's 3 — quick daily priority setting.

CRUD for a user's top 3 priorities for the day + lightweight suggestions.

Endpoints (per spec):
- GET /api/today
- POST /api/today
- PATCH /api/today/{id}
- POST /api/today/accept-suggestion
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.db.models import DailyPriority
from jarvis_server.db.session import get_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/today", tags=["today"])


class TodayPriorityOut(BaseModel):
    id: str
    position: int
    text: str
    completed: bool
    created_at: datetime
    source: str


class SuggestedPriorityOut(BaseModel):
    text: str
    reason: str
    confidence: float = Field(ge=0.0, le=1.0)


class TodayResponse(BaseModel):
    date: str
    priorities: list[TodayPriorityOut]
    suggested: list[SuggestedPriorityOut]


class SetTodayIn(BaseModel):
    priorities: list[dict[str, str]]


class PatchTodayIn(BaseModel):
    completed: bool


class AcceptSuggestionIn(BaseModel):
    text: str


def _today_cph() -> date:
    from zoneinfo import ZoneInfo

    return datetime.now(ZoneInfo("Europe/Copenhagen")).date()


async def _load_today(db: AsyncSession, d: date) -> list[DailyPriority]:
    q = select(DailyPriority).where(DailyPriority.date == d).order_by(DailyPriority.position)
    res = await db.execute(q)
    return list(res.scalars().all())


def _as_out(items: list[DailyPriority]) -> list[TodayPriorityOut]:
    return [
        TodayPriorityOut(
            id=i.id,
            position=i.position,
            text=i.text,
            completed=i.completed,
            created_at=i.created_at,
            source=i.source,
        )
        for i in items
    ]


async def _suggestions(db: AsyncSession, d: date, limit: int = 9) -> list[SuggestedPriorityOut]:
    """Generate suggestions based on available context.

    Heuristics (MVP):
    1) Carryover: yesterday's incomplete priorities.
    2) Upcoming meetings: today/tomorrow calendar events.
    3) Overdue promises: Promise records due/stale.
    4) Stale items: DetectedPattern unfinished/stale.
    """

    suggested: list[SuggestedPriorityOut] = []

    # 1) Carryover from yesterday
    try:
        yesterday = d - timedelta(days=1)
        q = select(DailyPriority).where(
            and_(DailyPriority.date == yesterday, DailyPriority.completed == False)  # noqa: E712
        )
        res = await db.execute(q)
        for item in res.scalars().all():
            suggested.append(
                SuggestedPriorityOut(
                    text=item.text,
                    reason="Carryover from yesterday (not completed)",
                    confidence=0.85,
                )
            )
    except Exception as e:
        logger.warning("today_suggest_carryover_error", error=str(e))

    # 2) Calendar events (today+tomorrow)
    try:
        from zoneinfo import ZoneInfo

        from jarvis_server.calendar.models import CalendarEvent

        cph = ZoneInfo("Europe/Copenhagen")
        start = datetime.combine(d, datetime.min.time(), tzinfo=cph)
        end = start + timedelta(days=2)
        q = (
            select(CalendarEvent)
            .where(
                and_(
                    CalendarEvent.start_time >= start.astimezone(timezone.utc),
                    CalendarEvent.start_time < end.astimezone(timezone.utc),
                )
            )
            .order_by(CalendarEvent.start_time)
            .limit(10)
        )
        res = await db.execute(q)
        for ev in res.scalars().all():
            start_local = ev.start_time.astimezone(cph) if ev.start_time.tzinfo else ev.start_time
            day_hint = "today" if start_local.date() == d else "tomorrow"
            suggested.append(
                SuggestedPriorityOut(
                    text=f"Prepare for: {ev.summary}",
                    reason=f"Meeting {day_hint} at {start_local.strftime('%H:%M')}",
                    confidence=0.75,
                )
            )
    except Exception as e:
        # Calendar module may be unused in some installs.
        logger.info("today_suggest_calendar_skipped", error=str(e))

    # 3) Promises
    try:
        from jarvis_server.db.models import Promise

        now_utc = datetime.now(timezone.utc)
        stale_cutoff = now_utc - timedelta(days=3)

        q = (
            select(Promise)
            .where(
                and_(
                    Promise.status == "pending",
                    func.coalesce(Promise.due_by, Promise.detected_at) <= now_utc,
                )
            )
            .order_by(desc(func.coalesce(Promise.due_by, Promise.detected_at)))
            .limit(10)
        )
        res = await db.execute(q)
        for p in res.scalars().all():
            conf = 0.7
            if p.detected_at and p.detected_at <= stale_cutoff:
                conf = 0.8
            suggested.append(
                SuggestedPriorityOut(
                    text=p.text.strip()[:240],
                    reason="Overdue commitment",
                    confidence=conf,
                )
            )
    except Exception as e:
        logger.info("today_suggest_promises_skipped", error=str(e))

    # 4) Detected patterns — unfinished/stale
    try:
        from jarvis_server.db.models import DetectedPattern

        stale_dt = datetime.now(timezone.utc) - timedelta(days=14)
        q = (
            select(DetectedPattern)
            .where(
                and_(
                    DetectedPattern.status == "active",
                    DetectedPattern.last_seen <= stale_dt,
                    DetectedPattern.pattern_type.in_(
                        ["unfinished_business", "stale_project", "broken_promise"]
                    ),
                )
            )
            .order_by(desc(DetectedPattern.last_seen))
            .limit(10)
        )
        res = await db.execute(q)
        for pat in res.scalars().all():
            text = (pat.suggested_action or pat.description).strip()[:240]
            suggested.append(
                SuggestedPriorityOut(
                    text=text,
                    reason=f"Stale: {pat.pattern_key} (last seen {pat.last_seen.date().isoformat()})",
                    confidence=0.6,
                )
            )
    except Exception as e:
        logger.info("today_suggest_patterns_skipped", error=str(e))

    # De-dupe by text and cap
    seen: set[str] = set()
    out: list[SuggestedPriorityOut] = []
    for s in suggested:
        key = s.text.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= limit:
            break

    return out


@router.get("", response_model=TodayResponse)
async def get_today(db: AsyncSession = Depends(get_db)) -> TodayResponse:
    d = _today_cph()
    items = await _load_today(db, d)
    suggested = await _suggestions(db, d)
    return TodayResponse(date=d.isoformat(), priorities=_as_out(items), suggested=suggested)


@router.post("", response_model=TodayResponse)
async def set_today(payload: SetTodayIn, db: AsyncSession = Depends(get_db)) -> TodayResponse:
    raw = payload.priorities or []
    texts = [str(x.get("text", "")).strip() for x in raw]
    texts = [t for t in texts if t]

    if len(texts) > 3:
        raise HTTPException(status_code=400, detail="Max 3 priorities allowed")

    d = _today_cph()

    # Replace all priorities for today.
    await db.execute(delete(DailyPriority).where(DailyPriority.date == d))

    created: list[DailyPriority] = []
    for idx, text in enumerate(texts, start=1):
        created.append(
            DailyPriority(
                date=d,
                position=idx,
                text=text,
                completed=False,
                completed_at=None,
                source="manual",
            )
        )

    db.add_all(created)
    await db.flush()

    logger.info("today_set", date=d.isoformat(), priorities=texts)

    items = await _load_today(db, d)
    suggested = await _suggestions(db, d)
    return TodayResponse(date=d.isoformat(), priorities=_as_out(items), suggested=suggested)


@router.patch("/{priority_id}", response_model=TodayPriorityOut)
async def patch_priority(
    priority_id: str, payload: PatchTodayIn, db: AsyncSession = Depends(get_db)
) -> TodayPriorityOut:
    res = await db.execute(select(DailyPriority).where(DailyPriority.id == priority_id))
    item = res.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Priority not found")

    item.completed = payload.completed
    item.completed_at = datetime.now(timezone.utc) if payload.completed else None
    await db.flush()

    logger.info("today_patch", id=priority_id, completed=item.completed)

    return TodayPriorityOut(
        id=item.id,
        position=item.position,
        text=item.text,
        completed=item.completed,
        created_at=item.created_at,
        source=item.source,
    )


@router.post("/accept-suggestion", response_model=TodayPriorityOut)
async def accept_suggestion(
    payload: AcceptSuggestionIn, db: AsyncSession = Depends(get_db)
) -> TodayPriorityOut:
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    d = _today_cph()
    items = await _load_today(db, d)
    if len(items) >= 3:
        raise HTTPException(status_code=400, detail="Already have 3 priorities")

    item = DailyPriority(
        date=d,
        position=len(items) + 1,
        text=text,
        completed=False,
        completed_at=None,
        source="suggested",
    )
    db.add(item)
    await db.flush()

    logger.info("today_accept_suggestion", date=d.isoformat(), text=text)

    return TodayPriorityOut(
        id=item.id,
        position=item.position,
        text=item.text,
        completed=item.completed,
        created_at=item.created_at,
        source=item.source,
    )
