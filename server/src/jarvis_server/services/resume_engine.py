"""Resume Engine - infer the user's last active project/thread from recent activity.

MVP heuristic implementation (no paid LLM calls):
- Look at recent screen captures (OCR text) in the last N hours
- Detect project candidates from file paths, known project names, and keywords
- Estimate time spent per project by summing capture-to-capture deltas (capped)
- Extract open files from OCR text
- Enrich with local git status/log when a repo can be located

This is intentionally lightweight and designed to improve over time via
`POST /api/resume/feedback`.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import structlog

logger = structlog.get_logger(__name__)


# Regexes tuned to OCR output (noisy, line breaks, etc.)
_FILE_RE = re.compile(
    r"(?P<path>(?:/|\\)[^\s\]\)\(<>\"']{2,}?(?:\.[a-zA-Z0-9]{1,6}))"
)

# Roughly matches POSIX-ish paths containing a recognizable project folder.
_PROJECT_PATH_HINTS: list[tuple[str, re.Pattern[str]]] = [
    ("Documents", re.compile(r"/Documents/(?P<proj>[A-Za-z0-9_.-]{2,})/")),
    ("dev", re.compile(r"/(?:dev|code|src)/(?P<proj>[A-Za-z0-9_.-]{2,})/")),
    ("git", re.compile(r"/(?:git|repos)/(?P<proj>[A-Za-z0-9_.-]{2,})/")),
]

# Keep a small whitelist to boost confidence for common projects in this repo.
# Reuse list from project_pulse.py without importing it (avoid import cycles).
KNOWN_PROJECTS = {
    "recruitos",
    "jarvis",
    "cmp",
    "sourcetrace",
    "atlas intelligence",
    "nerd",
    "koda",
    "danbolig",
    "source angel",
    "jbia",
    "clawdbot",
    "eureka",
    "dozy",
    "dronewatch",
    "skillsync",
}


@dataclass(frozen=True)
class CaptureSignal:
    id: str
    timestamp: datetime
    ocr_text: str


@dataclass
class ProjectStats:
    name: str
    duration_seconds: float
    last_active: datetime
    capture_ids: list[str]
    open_files: list[dict[str, str]]
    uncommitted_changes: bool = False
    repo_path: str | None = None
    recent_commits: list[dict[str, str]] | None = None


def _safe_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _human_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    mins = seconds // 60
    hours = mins // 60
    mins = mins % 60
    if hours <= 0:
        return f"{mins}m"
    return f"{hours}h {mins:02d}m"


def extract_file_paths(text: str, limit: int = 25) -> list[str]:
    """Extract file-like paths from OCR text."""
    if not text:
        return []

    hits: list[str] = []
    for m in _FILE_RE.finditer(text):
        p = m.group("path").strip().rstrip(":,.;")
        if len(p) < 4:
            continue
        hits.append(p)
        if len(hits) >= limit:
            break

    # De-dup preserving order
    seen = set()
    out = []
    for p in hits:
        if p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out


def detect_project_candidates(text: str) -> set[str]:
    """Detect project name candidates from OCR text.

    Sources:
    - Known projects (substring match)
    - Folder names from common path prefixes
    - GitHub-like `owner/repo` snippets (fallback)
    """
    if not text:
        return set()

    lowered = text.lower()
    candidates: set[str] = set()

    # Known projects
    for proj in KNOWN_PROJECTS:
        if proj in lowered:
            candidates.add(_normalize_project_name(proj))

    # Path-derived
    for _, rx in _PROJECT_PATH_HINTS:
        for m in rx.finditer(text):
            proj = m.group("proj")
            if proj:
                candidates.add(_normalize_project_name(proj))

    # owner/repo style
    for m in re.finditer(r"\b[A-Za-z0-9_.-]{2,}/(?P<repo>[A-Za-z0-9_.-]{2,})\b", text):
        candidates.add(_normalize_project_name(m.group("repo")))

    return {c for c in candidates if c}


def _normalize_project_name(name: str) -> str:
    name = (name or "").strip()
    # Keep original casing for multiword known projects (e.g. Atlas Intelligence)
    if name.lower() in KNOWN_PROJECTS:
        # title-case known multiword names, preserve single-word as-is if already capitalized
        if " " in name:
            return " ".join(w[:1].upper() + w[1:] for w in name.split())
        return name[:1].upper() + name[1:] if name and name[0].islower() else name

    # Otherwise: make it a nice display name
    if not name:
        return ""
    # Convert snake/kebab to words for display, but keep common repo capitalization simple
    cleaned = re.sub(r"[_-]+", " ", name).strip()
    if len(cleaned) <= 1:
        return ""
    return " ".join(w[:1].upper() + w[1:] for w in cleaned.split())


def estimate_durations(
    signals: list[CaptureSignal],
    project_for_signal: list[str | None],
    gap_cap_seconds: int = 120,
) -> dict[str, float]:
    """Estimate time spent per project by summing adjacent deltas.

    We cap each delta so a long idle gap doesn't attribute hours to a project.
    """
    if not signals:
        return {}

    # Sort by time asc (defensive)
    pairs = sorted(zip(signals, project_for_signal), key=lambda x: x[0].timestamp)

    durations: dict[str, float] = {}
    for (sig_a, proj_a), (sig_b, _proj_b) in zip(pairs, pairs[1:]):
        if not proj_a:
            continue
        delta = (sig_b.timestamp - sig_a.timestamp).total_seconds()
        if delta < 0:
            continue
        delta = min(delta, float(gap_cap_seconds))
        durations[proj_a] = durations.get(proj_a, 0.0) + delta

    # Last capture: attribute a small tail (half cap)
    last_sig, last_proj = pairs[-1]
    if last_proj:
        durations[last_proj] = durations.get(last_proj, 0.0) + gap_cap_seconds / 2

    return durations


def find_repo_for_project(project_name: str) -> Path | None:
    """Attempt to find a local git repo folder for a project.

    This is best-effort and intentionally conservative (no deep filesystem walks).
    """
    if not project_name:
        return None

    home = Path.home()
    candidates = []
    normalized = project_name.lower().replace(" ", "-")
    raw = project_name.lower().replace(" ", "")

    for base in (home / "Documents", home / "Code", home / "code", home / "dev"):
        if not base.exists():
            continue
        candidates.extend(
            [
                base / project_name,
                base / project_name.lower(),
                base / normalized,
                base / raw,
            ]
        )

    for c in candidates:
        if (c / ".git").exists():
            return c

    return None


def git_status_and_recent_commit(repo: Path) -> tuple[bool, list[dict[str, str]]]:
    """Return (is_dirty, recent_commits)."""
    is_dirty = False
    commits: list[dict[str, str]] = []

    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        is_dirty = bool(r.stdout.strip())
    except Exception as e:
        logger.debug("git_status_failed", repo=str(repo), error=str(e))

    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "log", "-5", "--pretty=%s|%ct"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            now = datetime.now(timezone.utc)
            for line in r.stdout.strip().splitlines():
                if "|" not in line:
                    continue
                msg, ts = line.rsplit("|", 1)
                try:
                    dt = datetime.fromtimestamp(int(ts), tz=timezone.utc)
                    commits.append({"message": msg.strip(), "time": _relative_time(now, dt)})
                except Exception:
                    continue
    except Exception as e:
        logger.debug("git_log_failed", repo=str(repo), error=str(e))

    return is_dirty, commits


def _relative_time(now: datetime, then: datetime) -> str:
    delta = now - then
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    mins = seconds // 60
    if mins < 60:
        return f"{mins}m ago"
    hours = mins // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def infer_last_decision_and_next_action(
    project_name: str,
    conversation_texts: Iterable[str],
    fallback_commit_message: str | None,
) -> tuple[str | None, str | None]:
    """Heuristic extraction of last decision + next action from text."""

    # Scan recent texts for explicit markers.
    decision_rx = re.compile(r"(?im)^(?:decision|decided|we decided)\s*[:\-]\s*(.+)$")
    next_rx = re.compile(r"(?im)^(?:next(?: action)?|todo|to-do)\s*[:\-]\s*(.+)$")

    last_decision = None
    next_action = None

    for t in conversation_texts:
        if not t:
            continue
        for m in decision_rx.finditer(t):
            last_decision = m.group(1).strip()
        for m in next_rx.finditer(t):
            next_action = m.group(1).strip()

    if not last_decision and fallback_commit_message:
        last_decision = fallback_commit_message

    if not next_action:
        # Reasonable default: keep it actionable but non-lying.
        next_action = f"Continue work on {project_name}" if project_name else None

    return last_decision, next_action


def build_resume_from_captures(
    signals: list[CaptureSignal],
    now: datetime | None = None,
) -> tuple[ProjectStats | None, dict]:
    """Build ProjectStats for the dominant project and a `why` dict."""

    if now is None:
        now = datetime.now(timezone.utc)

    if not signals:
        return None, {
            "reasons": ["No recent captures"],
            "confidence": 0.0,
            "sources": [],
        }

    # Determine project per signal
    signal_projects: list[str | None] = []
    per_project_capture_ids: dict[str, list[str]] = {}
    per_project_last_active: dict[str, datetime] = {}
    per_project_files: dict[str, list[str]] = {}

    for sig in signals:
        candidates = detect_project_candidates(sig.ocr_text)
        proj = None
        if candidates:
            # Prefer longest (often more specific, e.g. "Atlas Intelligence")
            proj = sorted(candidates, key=len, reverse=True)[0]
        signal_projects.append(proj)

        if proj:
            per_project_capture_ids.setdefault(proj, []).append(sig.id)
            per_project_last_active[proj] = max(
                per_project_last_active.get(proj, sig.timestamp), sig.timestamp
            )
            per_project_files.setdefault(proj, []).extend(extract_file_paths(sig.ocr_text))

    durations = estimate_durations(signals, signal_projects)

    if not durations:
        # Fallback: most recent capture that has any project
        for sig, proj in reversed(list(zip(signals, signal_projects))):
            if proj:
                durations[proj] = 1.0
                per_project_last_active[proj] = sig.timestamp
                per_project_capture_ids.setdefault(proj, []).append(sig.id)
                per_project_files.setdefault(proj, []).extend(extract_file_paths(sig.ocr_text))
                break

    if not durations:
        return None, {
            "reasons": ["No project detected in recent captures"],
            "confidence": 0.0,
            "sources": [{"kind": "capture", "id": s.id, "timestamp": _safe_iso(s.timestamp)} for s in signals[-5:]],
        }

    dominant = max(durations.items(), key=lambda kv: kv[1])[0]
    dominant_duration = durations[dominant]
    total_duration = sum(durations.values()) or 1.0
    confidence = min(0.99, max(0.2, dominant_duration / total_duration))

    # Open files: de-dup and format
    files = per_project_files.get(dominant, [])
    # Prefer paths that look like source files.
    files = [f for f in files if re.search(r"\.(?:ts|tsx|js|jsx|py|css|md|json|yml|yaml)$", f, re.I)]
    seen = set()
    open_files = []
    for f in files:
        if f in seen:
            continue
        seen.add(f)
        open_files.append({"name": Path(f).name, "path": f})
        if len(open_files) >= 10:
            break

    # Today's duration (UTC day)
    midnight = now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    today_signals = [s for s, p in zip(signals, signal_projects) if p == dominant and s.timestamp >= midnight]
    if len(today_signals) >= 2:
        today_durations = estimate_durations(today_signals, [dominant] * len(today_signals))
        duration_today_s = today_durations.get(dominant, 0.0)
    else:
        duration_today_s = dominant_duration

    reasons = [
        "Most recent activity",
        f"{len(open_files)} file(s) detected on screen",
    ]

    sources = [
        {
            "kind": "capture",
            "id": cid,
        }
        for cid in per_project_capture_ids.get(dominant, [])[-5:]
    ]

    stats = ProjectStats(
        name=dominant,
        duration_seconds=duration_today_s,
        last_active=per_project_last_active.get(dominant, max(s.timestamp for s in signals)),
        capture_ids=per_project_capture_ids.get(dominant, []),
        open_files=open_files,
    )

    # Git enrichment
    repo = find_repo_for_project(dominant)
    if repo:
        dirty, commits = git_status_and_recent_commit(repo)
        stats.uncommitted_changes = dirty
        stats.repo_path = str(repo)
        stats.recent_commits = commits
        if dirty:
            reasons.append("Uncommitted changes")
            sources.append({"kind": "git", "repo": str(repo), "signal": "dirty"})
        if commits:
            sources.append({"kind": "git", "repo": str(repo), "signal": "recent_commits"})

    why = {
        "reasons": reasons,
        "confidence": round(float(confidence), 2),
        "sources": sources,
    }

    return stats, why


def append_feedback(storage_dir: Path, payload: dict) -> None:
    storage_dir.mkdir(parents=True, exist_ok=True)
    path = storage_dir / "resume_feedback.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
