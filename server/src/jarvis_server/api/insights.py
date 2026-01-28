"""Proactive insights API."""

import structlog
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from jarvis_server.notifications.insights import detect_all_insights
from jarvis_server.notifications.tasks import check_and_notify

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v2/insights", tags=["insights"])


class InsightResponse(BaseModel):
    """A proactive insight."""
    message: str
    priority: int


class InsightsListResponse(BaseModel):
    """List of current insights."""
    insights: list[InsightResponse]
    count: int


@router.get("", response_model=InsightsListResponse)
async def get_insights() -> InsightsListResponse:
    """Get current proactive insights without sending notifications.
    
    Useful for previewing what insights would be sent.
    """
    try:
        insights = await detect_all_insights()
        
        return InsightsListResponse(
            insights=[
                InsightResponse(message=i.message, priority=i.priority)
                for i in insights
            ],
            count=len(insights),
        )
    except Exception as e:
        logger.error("get_insights_failed", error=str(e), exc_info=True)
        return InsightsListResponse(insights=[], count=0)


@router.post("/notify")
async def trigger_notifications(background_tasks: BackgroundTasks) -> dict:
    """Manually trigger proactive notification check.
    
    Runs the notification task in the background.
    """
    background_tasks.add_task(check_and_notify)
    logger.info("notification_check_triggered_manually")
    
    return {
        "status": "scheduled",
        "message": "Notification check queued in background",
    }
