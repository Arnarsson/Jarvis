"""Application usage insights API."""

import structlog
from fastapi import APIRouter
from pydantic import BaseModel

from jarvis_server.analytics.app_usage import (
    analyze_app_usage,
    get_usage_insights,
    detect_context_switches,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v2/app-insights", tags=["analytics"])


class AppUsageResponse(BaseModel):
    """Application usage statistics."""
    app_name: str
    total_captures: int
    peak_hour: int
    first_seen: str
    last_seen: str


class UsageInsightResponse(BaseModel):
    """Usage insight message."""
    type: str
    message: str
    metadata: dict | None = None


class AppInsightsResponse(BaseModel):
    """Complete app insights response."""
    insights: list[UsageInsightResponse]
    top_apps: list[AppUsageResponse]
    context_switches_24h: int


@router.get("", response_model=AppInsightsResponse)
async def get_app_insights(days: int = 7) -> AppInsightsResponse:
    """Get application usage insights and statistics.
    
    Analyzes screen captures to detect:
    - Most-used applications
    - Peak usage hours
    - Context switching patterns
    - App diversity
    
    Args:
        days: Number of days to analyze (default: 7)
    """
    try:
        # Get insights
        insights = await get_usage_insights()
        
        # Get top apps
        usage_stats = await analyze_app_usage(days=days)
        top_apps = [
            AppUsageResponse(
                app_name=stat.app_name,
                total_captures=stat.total_captures,
                peak_hour=stat.peak_hour,
                first_seen=stat.first_seen.isoformat(),
                last_seen=stat.last_seen.isoformat(),
            )
            for stat in usage_stats[:10]  # Top 10 apps
        ]
        
        # Get context switches
        switches = await detect_context_switches()
        
        # Format insights
        formatted_insights = []
        for insight in insights:
            metadata = {k: v for k, v in insight.items() if k not in ["type", "message"]}
            formatted_insights.append(
                UsageInsightResponse(
                    type=insight["type"],
                    message=insight["message"],
                    metadata=metadata if metadata else None,
                )
            )
        
        logger.info(
            "app_insights_retrieved",
            insights_count=len(formatted_insights),
            apps_count=len(top_apps),
        )
        
        return AppInsightsResponse(
            insights=formatted_insights,
            top_apps=top_apps,
            context_switches_24h=len(switches),
        )
        
    except Exception as e:
        logger.error("app_insights_failed", error=str(e), exc_info=True)
        return AppInsightsResponse(
            insights=[],
            top_apps=[],
            context_switches_24h=0,
        )


@router.get("/top-apps", response_model=list[AppUsageResponse])
async def get_top_apps(days: int = 7, limit: int = 10) -> list[AppUsageResponse]:
    """Get most-used applications.
    
    Args:
        days: Number of days to analyze
        limit: Maximum number of apps to return
    """
    try:
        usage_stats = await analyze_app_usage(days=days)
        
        return [
            AppUsageResponse(
                app_name=stat.app_name,
                total_captures=stat.total_captures,
                peak_hour=stat.peak_hour,
                first_seen=stat.first_seen.isoformat(),
                last_seen=stat.last_seen.isoformat(),
            )
            for stat in usage_stats[:limit]
        ]
        
    except Exception as e:
        logger.error("top_apps_failed", error=str(e), exc_info=True)
        return []
