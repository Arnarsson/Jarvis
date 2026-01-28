"""Activity summary API — hourly summaries from OCR-extracted screen captures."""

import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.db.models import Capture
from jarvis_server.db.session import get_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/activity", tags=["activity"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class HourBlock(BaseModel):
    """One hour of activity."""
    hour: int = Field(description="Hour of day (0-23)")
    start: str = Field(description="ISO timestamp of first capture in this hour")
    end: str = Field(description="ISO timestamp of last capture in this hour")
    capture_count: int = Field(description="Number of screenshots in this hour")
    summary: str = Field(description="Condensed summary of activity")
    apps: list[str] = Field(description="Detected applications/windows")
    topics: list[str] = Field(description="Key topics/tasks detected")
    sample_capture_id: Optional[str] = Field(default=None, description="ID of a representative capture")


class DaySummary(BaseModel):
    """Full day activity summary."""
    date: str
    total_captures: int
    active_hours: int
    hours: list[HourBlock]


# ── OCR Analysis Helpers ─────────────────────────────────────────────────────

# Common app/window patterns to detect
APP_PATTERNS = {
    "VS Code": r"(?:Visual Studio Code|\.tsx|\.py|\.ts|\.js|\.md|code-oss)",
    "Terminal": r"(?:bash|zsh|pts/\d|terminal|\$ |❯|sven@|root@)",
    "Slack": r"(?:Slack|#\w+|Direct messages|Huddles|Channels)",
    "Browser": r"(?:Google Chrome|Firefox|Brave|localhost|https?://)",
    "Telegram": r"(?:Telegram|@\w+arsson)",
    "Email": r"(?:Gmail|Inbox|unread|email|priority)",
    "Claude": r"(?:Claude|Anthropic|claude\.ai|Claude Code)",
    "GitHub": r"(?:github\.com|Pull Request|Issues|gh pr|gh issue)",
    "Docker": r"(?:docker|container|compose|jarvis-\w+)",
    "Calendar": r"(?:Google Calendar|meeting|calendar|schedule)",
}

NOISE_PATTERNS = re.compile(
    r"(?:^[^a-zA-Z0-9]*$|^.{0,2}$|^[—=\-_|/\\]+$|^\d+$)",
    re.MULTILINE,
)


def clean_ocr_text(raw: str) -> str:
    """Clean OCR text — remove noise lines, excessive whitespace."""
    lines = raw.split("\n")
    cleaned = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if NOISE_PATTERNS.match(line):
            continue
        if len(line) < 3:
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def detect_apps(text: str) -> list[str]:
    """Detect which applications are visible in the OCR text."""
    apps = []
    for app_name, pattern in APP_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            apps.append(app_name)
    return apps


def extract_topics(text: str) -> list[str]:
    """Extract key topics/tasks from OCR text."""
    topics = []

    # Look for file paths (indicates coding)
    files = re.findall(r"[\w/]+\.(?:tsx?|jsx?|py|md|css|html|json|yml)", text)
    if files:
        unique_files = list(dict.fromkeys(files))[:5]
        topics.append(f"Editing: {', '.join(unique_files)}")

    # Look for git/PR activity
    if re.search(r"(?:commit|merge|pull request|branch|push)", text, re.IGNORECASE):
        topics.append("Git/PR activity")

    # Look for URLs/domains
    domains = re.findall(r"(?:localhost:\d+|[\w-]+\.(?:com|io|dev|org|dk))", text)
    if domains:
        unique_domains = list(dict.fromkeys(domains))[:3]
        topics.append(f"Sites: {', '.join(unique_domains)}")

    # Look for Danish text (indicates personal comms)
    if re.search(r"\b(?:har|ikke|kan|det|til|med|også|eller|hvad|godt)\b", text):
        topics.append("Danish communications")

    # Look for specific project names
    if re.search(r"jarvis|dashboard", text, re.IGNORECASE):
        topics.append("Jarvis project")
    if re.search(r"atlas|intelligence", text, re.IGNORECASE):
        topics.append("Atlas Intelligence")
    if re.search(r"clawdbot|eureka", text, re.IGNORECASE):
        topics.append("Clawdbot/Eureka")
    if re.search(r"recrui|skillsync", text, re.IGNORECASE):
        topics.append("SkillSync/RecruiTOS")

    return list(dict.fromkeys(topics))[:8]


def summarize_hour(captures_text: list[str], apps: list[str], topics: list[str]) -> str:
    """Generate a human-readable summary for an hour block."""
    parts = []

    if apps:
        parts.append(f"Active in: {', '.join(apps)}")

    if topics:
        parts.append(f"Working on: {', '.join(topics)}")

    if not parts:
        parts.append("Screen activity (no clear text detected)")

    return " · ".join(parts)


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/summary", response_model=DaySummary)
async def get_day_summary(
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format, defaults to today"),
    session: AsyncSession = Depends(get_db),
):
    """Get hourly activity summary for a given day."""
    if date:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    else:
        target_date = datetime.now(timezone.utc).date()

    # Fetch all captures for the day that have OCR text
    start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=timezone.utc)

    result = await session.execute(
        select(Capture)
        .where(
            and_(
                Capture.timestamp >= start,
                Capture.timestamp <= end,
                Capture.ocr_text.isnot(None),
            )
        )
        .order_by(Capture.timestamp)
    )
    captures = list(result.scalars().all())

    # Group by hour
    by_hour: dict[int, list] = defaultdict(list)
    for c in captures:
        hour = c.timestamp.hour
        by_hour[hour].append(c)

    # Build hour blocks
    hours = []
    for hour in sorted(by_hour.keys()):
        hour_captures = by_hour[hour]

        # Combine OCR text from all captures in this hour
        all_text = []
        for c in hour_captures:
            cleaned = clean_ocr_text(c.ocr_text or "")
            if cleaned:
                all_text.append(cleaned)

        combined = "\n---\n".join(all_text)
        apps = detect_apps(combined)
        topics = extract_topics(combined)
        summary = summarize_hour(all_text, apps, topics)

        hours.append(HourBlock(
            hour=hour,
            start=hour_captures[0].timestamp.isoformat(),
            end=hour_captures[-1].timestamp.isoformat(),
            capture_count=len(hour_captures),
            summary=summary,
            apps=apps,
            topics=topics,
            sample_capture_id=hour_captures[len(hour_captures) // 2].id,
        ))

    return DaySummary(
        date=target_date.isoformat(),
        total_captures=len(captures),
        active_hours=len(hours),
        hours=hours,
    )


@router.get("/hours")
async def get_active_hours(
    days: int = Query(7, ge=1, le=30),
    session: AsyncSession = Depends(get_db),
):
    """Get active hours heatmap data for the last N days."""
    cutoff = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    cutoff = cutoff.replace(day=cutoff.day - days + 1) if days > 1 else cutoff

    result = await session.execute(
        select(
            func.date(Capture.timestamp).label("date"),
            func.extract("hour", Capture.timestamp).label("hour"),
            func.count(Capture.id).label("count"),
        )
        .where(Capture.timestamp >= cutoff)
        .group_by("date", "hour")
        .order_by("date", "hour")
    )
    rows = result.all()

    return [
        {"date": str(r.date), "hour": int(r.hour), "count": r.count}
        for r in rows
    ]
