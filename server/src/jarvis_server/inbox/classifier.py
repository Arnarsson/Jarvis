"""Focus Inbox triage classifier (v1).

Splits incoming comms into Priority vs Rest with an explainable `why_priority` payload.

Rules (v1 - simple):
- VIP sender
- Question detected
- Deadline mention
- Relationship stale
- Action required

Priority threshold:
- VIP sender => Priority
- Else >= 2 rules matched => Priority

This module is intentionally heuristic and deterministic (no LLM calls).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass(frozen=True)
class RuleMatch:
    key: str
    label: str
    confidence: float
    sources: list[dict[str, Any]]


QUESTION_PATTERNS = [
    re.compile(r"\?"),
    re.compile(r"\bcan you\b", re.IGNORECASE),
    re.compile(r"\bcould you\b", re.IGNORECASE),
    re.compile(r"\bwill you\b", re.IGNORECASE),
]

ACTION_REQUIRED_PATTERNS = [
    re.compile(r"\bplease\b", re.IGNORECASE),
    re.compile(r"\bneed you to\b", re.IGNORECASE),
    re.compile(r"\baction item\b", re.IGNORECASE),
]

DEADLINE_PATTERNS = [
    re.compile(r"\basap\b", re.IGNORECASE),
    re.compile(r"\burgent\b", re.IGNORECASE),
    re.compile(r"\bby tomorrow\b", re.IGNORECASE),
    re.compile(r"\bby end of day\b", re.IGNORECASE),
    re.compile(r"\beod\b", re.IGNORECASE),
    # Very lightweight date mentions: 2026-01-28, 28/01, 28 Jan, Jan 28
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b\d{1,2}/\d{1,2}\b"),
    re.compile(r"\b\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\b", re.IGNORECASE),
    re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)\s+\d{1,2}\b", re.IGNORECASE),
]


def _norm_email(addr: str | None) -> str:
    return (addr or "").strip().lower()


def _text_blob(*parts: str | None) -> str:
    return "\n".join([p for p in (parts or []) if p]).strip()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _match_any(patterns: list[re.Pattern[str]], text: str) -> list[str]:
    hits: list[str] = []
    for pat in patterns:
        if pat.search(text):
            hits.append(pat.pattern)
    return hits


def classify_focus_inbox_item(
    *,
    from_address: str | None,
    subject: str | None,
    snippet: str | None,
    body_text: str | None,
    received_at: datetime,
    previous_contact_at: datetime | None,
    vip_senders: set[str],
) -> dict[str, Any]:
    """Classify a message for Focus Inbox.

    Returns a dict with:
      - is_priority: bool
      - why_priority: { reasons: [...], confidence: float, sources: [...] }
      - matched_rules: list[str]
    """

    from_norm = _norm_email(from_address)
    blob = _text_blob(subject, snippet, body_text)

    matches: list[RuleMatch] = []

    # Rule: VIP sender
    if from_norm and from_norm in vip_senders:
        matches.append(
            RuleMatch(
                key="vip_sender",
                label="Sender is VIP",
                confidence=0.95,
                sources=[{"field": "from", "value": from_address}],
            )
        )

    # Rule: Question detected
    q_hits = _match_any(QUESTION_PATTERNS, blob)
    if q_hits:
        matches.append(
            RuleMatch(
                key="question_detected",
                label="Question detected",
                confidence=0.75,
                sources=[
                    {"field": "text", "value": (subject or snippet or "")[:200], "match": "? / question phrase"}
                ],
            )
        )

    # Rule: Deadline mention
    d_hits = _match_any(DEADLINE_PATTERNS, blob)
    if d_hits:
        matches.append(
            RuleMatch(
                key="deadline_mention",
                label="Contains deadline mention",
                confidence=0.8,
                sources=[
                    {"field": "text", "value": (subject or snippet or "")[:200], "match": "deadline keyword/date"}
                ],
            )
        )

    # Rule: Action required
    a_hits = _match_any(ACTION_REQUIRED_PATTERNS, blob)
    if a_hits:
        matches.append(
            RuleMatch(
                key="action_required",
                label="Action required",
                confidence=0.7,
                sources=[
                    {"field": "text", "value": (subject or snippet or "")[:200], "match": "please/need you"}
                ],
            )
        )

    # Rule: Relationship stale
    stale_threshold = timedelta(days=30)
    if previous_contact_at is None:
        # If we've never seen this sender, treat as a "stale / needs attention" signal but lower confidence.
        matches.append(
            RuleMatch(
                key="relationship_stale",
                label="Relationship stale",
                confidence=0.55,
                sources=[{"field": "history", "value": "No previous contact found"}],
            )
        )
    else:
        if (received_at - previous_contact_at) > stale_threshold:
            matches.append(
                RuleMatch(
                    key="relationship_stale",
                    label="Relationship stale",
                    confidence=0.65,
                    sources=[
                        {
                            "field": "history",
                            "value": f"Last contact was {(received_at - previous_contact_at).days} days ago",
                            "previous_contact_at": previous_contact_at.isoformat(),
                        }
                    ],
                )
            )

    # Priority decision
    is_vip = any(m.key == "vip_sender" for m in matches)
    non_vip_match_count = len([m for m in matches if m.key != "vip_sender"])
    is_priority = bool(is_vip or non_vip_match_count >= 2)

    # Confidence heuristic: base on match count + strength of signals.
    if is_vip:
        conf = 0.92
        if non_vip_match_count >= 2:
            conf = 0.95
    else:
        conf = min(0.9, 0.35 + 0.2 * non_vip_match_count)
        if not is_priority:
            conf = min(conf, 0.55)

    why = {
        "reasons": [m.label for m in matches],
        "confidence": round(conf, 2),
        "sources": [s for m in matches for s in m.sources],
    }

    return {
        "is_priority": is_priority,
        "why_priority": why,
        "matched_rules": [m.key for m in matches],
    }
