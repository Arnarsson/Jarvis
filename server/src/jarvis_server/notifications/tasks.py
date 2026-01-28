"""Background tasks for proactive notifications."""

import structlog
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

from jarvis_server.config import get_settings
from .insights import detect_all_insights
from .telegram import send_telegram_notification

logger = structlog.get_logger(__name__)

# Track when we last sent notifications to avoid spam
NOTIFICATION_STATE_FILE = Path("/tmp/jarvis-notification-state.json")


def _load_notification_state() -> dict:
    """Load the last notification state."""
    if not NOTIFICATION_STATE_FILE.exists():
        return {"last_run": None, "sent_insights": []}
    
    try:
        with open(NOTIFICATION_STATE_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error("failed_to_load_notification_state", error=str(e))
        return {"last_run": None, "sent_insights": []}


def _save_notification_state(state: dict) -> None:
    """Save the notification state."""
    try:
        with open(NOTIFICATION_STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception as e:
        logger.error("failed_to_save_notification_state", error=str(e))


async def check_and_notify() -> None:
    """Check for proactive insights and send notifications.
    
    This task runs periodically (e.g., every 6 hours) to:
    1. Detect follow-up opportunities and other insights
    2. Send top insights via Telegram
    3. Track what was sent to avoid duplicates
    """
    logger.info("proactive_notification_check_starting")
    
    # Load state
    state = _load_notification_state()
    last_run = state.get("last_run")
    sent_insights = set(state.get("sent_insights", []))
    
    # Don't run more than once every 4 hours
    if last_run:
        last_run_time = datetime.fromisoformat(last_run)
        if datetime.now(timezone.utc) - last_run_time < timedelta(hours=4):
            logger.info(
                "proactive_notification_check_skipped",
                reason="too_soon",
                last_run=last_run,
            )
            return
    
    # Detect insights
    insights = await detect_all_insights()
    
    if not insights:
        logger.info("no_insights_detected")
        state["last_run"] = datetime.now(timezone.utc).isoformat()
        _save_notification_state(state)
        return
    
    # Send top insights (max 3 per run to avoid spam)
    sent_count = 0
    new_sent = []
    
    for insight in insights[:3]:
        # Skip if we've already sent this insight recently
        insight_key = insight.message[:100]  # Use first 100 chars as key
        if insight_key in sent_insights:
            continue
        
        # Send notification
        success = await send_telegram_notification(
            message=f"💡 **Jarvis Insight**\n\n{insight.message}",
            silent=insight.priority < 2,  # High priority = notification sound
        )
        
        if success:
            sent_count += 1
            new_sent.append(insight_key)
            logger.info(
                "insight_notification_sent",
                message=insight.message,
                priority=insight.priority,
            )
    
    # Update state
    # Keep last 50 sent insights to avoid memory growth
    all_sent = list(sent_insights) + new_sent
    state["sent_insights"] = all_sent[-50:]
    state["last_run"] = datetime.now(timezone.utc).isoformat()
    _save_notification_state(state)
    
    logger.info(
        "proactive_notification_check_complete",
        insights_detected=len(insights),
        notifications_sent=sent_count,
    )
