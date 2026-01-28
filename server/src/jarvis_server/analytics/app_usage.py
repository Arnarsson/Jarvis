"""Application usage pattern detection from screen captures."""

import re
import structlog
from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter
from typing import List, Dict, Tuple
from sqlalchemy import select, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.db.session import AsyncSessionLocal
from jarvis_server.db.models import Capture

logger = structlog.get_logger(__name__)

# Application signatures: regex patterns and keywords to detect apps
APP_SIGNATURES = {
    "Chrome": [
        r"chrome",
        r"google",
        r"://",
        r"https?:",
        r"\.com",
    ],
    "VS Code": [
        r"visual\s*studio\s*code",
        r"vscode",
        r"\.py",
        r"\.js",
        r"\.ts",
        r"def\s+\w+",
        r"import\s+",
        r"function\s+",
    ],
    "Terminal": [
        r"\$\s",
        r"bash",
        r"zsh",
        r"~/",
        r"sudo",
        r"docker",
        r"git\s+",
        r"npm\s+",
        r"python\s+",
    ],
    "Slack": [
        r"slack",
        r"#\w+\s+channel",
        r"direct\s*message",
    ],
    "Telegram": [
        r"telegram",
        r"@\w+",
    ],
    "Discord": [
        r"discord",
        r"#general",
        r"#\w+\s+\d+\s+online",
    ],
    "Linear": [
        r"linear",
        r"backlog",
        r"in\s+progress",
        r"todo",
        r"issue\s+#",
    ],
    "Figma": [
        r"figma",
        r"design\s+file",
        r"frame\s+\d+",
    ],
    "Notion": [
        r"notion",
        r"workspace",
        r"database",
    ],
    "Calendar": [
        r"google\s+calendar",
        r"calendar",
        r"meeting",
        r"\d{1,2}:\d{2}\s*[AP]M",
        r"event",
    ],
    "Email": [
        r"gmail",
        r"inbox",
        r"compose",
        r"subject:",
        r"from:",
        r"to:",
    ],
}


def detect_app(ocr_text: str) -> str:
    """Detect the most likely application from OCR text.
    
    Args:
        ocr_text: Raw OCR text from screen capture
        
    Returns:
        Application name (e.g., "Chrome", "VS Code") or "Unknown"
    """
    if not ocr_text:
        return "Unknown"
    
    text_lower = ocr_text.lower()
    scores = defaultdict(int)
    
    # Score each app based on pattern matches
    for app, patterns in APP_SIGNATURES.items():
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                scores[app] += 1
    
    # Return app with highest score, or "Unknown" if no matches
    if not scores:
        return "Unknown"
    
    best_app = max(scores.items(), key=lambda x: x[1])
    
    # Require at least 2 matches to be confident
    if best_app[1] >= 2:
        return best_app[0]
    
    return "Unknown"


class AppUsageStats:
    """Application usage statistics."""
    
    def __init__(
        self,
        app_name: str,
        total_captures: int,
        hours_by_hour: Dict[int, int],
        first_seen: datetime,
        last_seen: datetime,
    ):
        self.app_name = app_name
        self.total_captures = total_captures
        self.hours_by_hour = hours_by_hour  # Hour of day (0-23) -> capture count
        self.first_seen = first_seen
        self.last_seen = last_seen
    
    @property
    def peak_hour(self) -> int:
        """Hour of day with most activity (0-23)."""
        if not self.hours_by_hour:
            return 0
        return max(self.hours_by_hour.items(), key=lambda x: x[1])[0]
    
    @property
    def usage_percentage(self) -> float:
        """Percentage of total captures."""
        # This will be calculated by the analyzer
        return 0.0


async def analyze_app_usage(
    days: int = 7,
    min_captures: int = 5,
) -> List[AppUsageStats]:
    """Analyze application usage patterns from screen captures.
    
    Args:
        days: Number of days to analyze
        min_captures: Minimum captures for an app to be included
        
    Returns:
        List of AppUsageStats sorted by usage count
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    
    async with AsyncSessionLocal() as db:
        # Fetch captures with OCR text from the time period
        result = await db.execute(
            select(Capture)
            .where(
                and_(
                    Capture.timestamp >= since,
                    Capture.ocr_text.isnot(None),
                    Capture.processing_status == "completed",
                )
            )
            .order_by(Capture.timestamp)
        )
        captures = result.scalars().all()
    
    if not captures:
        logger.info("no_captures_found_for_analysis", days=days)
        return []
    
    # Analyze each capture
    app_data = defaultdict(lambda: {
        "count": 0,
        "hours": defaultdict(int),
        "timestamps": [],
    })
    
    for capture in captures:
        app = detect_app(capture.ocr_text)
        app_data[app]["count"] += 1
        app_data[app]["hours"][capture.timestamp.hour] += 1
        app_data[app]["timestamps"].append(capture.timestamp)
    
    # Build stats objects
    stats = []
    total_captures = len(captures)
    
    for app, data in app_data.items():
        if data["count"] < min_captures:
            continue
        
        stats_obj = AppUsageStats(
            app_name=app,
            total_captures=data["count"],
            hours_by_hour=dict(data["hours"]),
            first_seen=min(data["timestamps"]),
            last_seen=max(data["timestamps"]),
        )
        stats.append(stats_obj)
    
    # Sort by usage count
    stats.sort(key=lambda x: x.total_captures, reverse=True)
    
    logger.info(
        "app_usage_analysis_complete",
        days=days,
        total_captures=total_captures,
        unique_apps=len(stats),
    )
    
    return stats


async def detect_context_switches() -> List[Dict]:
    """Detect rapid context switching between applications.
    
    Context switching is when you switch between different apps
    frequently, which can indicate distraction or multitasking.
    
    Returns:
        List of context switch events with timing and apps
    """
    # Analyze last 24 hours
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Capture)
            .where(
                and_(
                    Capture.timestamp >= since,
                    Capture.ocr_text.isnot(None),
                    Capture.processing_status == "completed",
                )
            )
            .order_by(Capture.timestamp)
        )
        captures = result.scalars().all()
    
    if len(captures) < 2:
        return []
    
    # Detect switches
    switches = []
    prev_app = None
    switch_count = 0
    
    for capture in captures:
        current_app = detect_app(capture.ocr_text)
        
        if prev_app and current_app != prev_app and current_app != "Unknown":
            switch_count += 1
            switches.append({
                "from_app": prev_app,
                "to_app": current_app,
                "timestamp": capture.timestamp,
            })
        
        prev_app = current_app
    
    logger.info(
        "context_switches_detected",
        total_switches=len(switches),
        captures_analyzed=len(captures),
    )
    
    return switches


async def get_usage_insights() -> List[Dict]:
    """Generate human-readable insights from app usage data.
    
    Returns:
        List of insight dictionaries with message and metadata
    """
    insights = []
    
    # Analyze usage patterns
    stats = await analyze_app_usage(days=7)
    
    if not stats:
        return insights
    
    # Top app insight
    top_app = stats[0]
    insights.append({
        "type": "top_app",
        "message": f"📊 Your most-used app this week: **{top_app.app_name}** ({top_app.total_captures} captures)",
        "app": top_app.app_name,
        "count": top_app.total_captures,
    })
    
    # Peak productivity hour
    if top_app.hours_by_hour:
        peak_hour = top_app.peak_hour
        hour_12 = peak_hour if peak_hour <= 12 else peak_hour - 12
        am_pm = "AM" if peak_hour < 12 else "PM"
        insights.append({
            "type": "peak_hour",
            "message": f"⏰ You're most active in **{top_app.app_name}** around **{hour_12}:00 {am_pm}**",
            "hour": peak_hour,
            "app": top_app.app_name,
        })
    
    # Context switching analysis
    switches = await detect_context_switches()
    if len(switches) > 50:  # More than 50 switches in 24h = high
        insights.append({
            "type": "context_switching",
            "message": f"⚠️ High context switching detected: **{len(switches)}** app switches in 24h. Consider time-blocking.",
            "switch_count": len(switches),
        })
    
    # App diversity
    if len(stats) > 8:
        insights.append({
            "type": "app_diversity",
            "message": f"🎯 Using **{len(stats)}** different apps this week. Consider consolidating workflows.",
            "unique_apps": len(stats),
        })
    
    return insights
