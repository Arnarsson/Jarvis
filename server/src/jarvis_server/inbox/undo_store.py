"""In-memory undo store for Focus Inbox bulk actions.

MVP implementation: process-local storage with TTL.

If/when Jarvis runs multiple worker processes, this should move to Redis.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class UndoRecord:
    ids: list[str]
    expires_at: datetime


_UNDO: dict[str, UndoRecord] = {}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _gc() -> None:
    now = _now_utc()
    expired = [t for t, r in _UNDO.items() if r.expires_at <= now]
    for t in expired:
        _UNDO.pop(t, None)


def create_undo_token(*, ids: list[str], ttl_minutes: int = 10) -> tuple[str, datetime]:
    _gc()
    token = secrets.token_urlsafe(24)
    expires_at = _now_utc() + timedelta(minutes=ttl_minutes)
    _UNDO[token] = UndoRecord(ids=ids, expires_at=expires_at)
    return token, expires_at


def pop_undo_ids(token: str) -> UndoRecord | None:
    _gc()
    rec = _UNDO.pop(token, None)
    if rec is None:
        return None
    if rec.expires_at <= _now_utc():
        return None
    return rec


def peek_undo(token: str) -> UndoRecord | None:
    _gc()
    rec = _UNDO.get(token)
    if rec is None or rec.expires_at <= _now_utc():
        return None
    return rec
