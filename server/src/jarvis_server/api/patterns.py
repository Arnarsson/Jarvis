"""Detected Patterns API - access behavioral patterns from LLM analysis.

Provides endpoints to query and trigger detection of behavioral patterns
using LLM-based analysis of conversations, screen captures, and activity data.
"""

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.api.helpers import build_why_from_pattern
from jarvis_server.api.models import WhyPayload
from jarvis_server.db.session import get_db
from jarvis_server.db.models import DetectedPattern

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v2/patterns", tags=["patterns"])


# Response Models
class PatternResponse(BaseModel):
    """Single detected pattern."""
    id: str
    pattern_type: str
    pattern_key: str
    description: str
    frequency: int
    first_seen: str
    last_seen: str
    suggested_action: str | None
    conversation_ids: list[str]
    detected_at: str
    status: str
    why: WhyPayload | None = None


class PatternsListResponse(BaseModel):
    """List of detected patterns."""
    patterns: list[PatternResponse]
    total: int
    by_type: dict[str, int]


class DetectionResponse(BaseModel):
    """Response from triggering pattern detection."""
    status: str
    message: str
    patterns_found: int | None = None


@router.get("", response_model=PatternsListResponse)
async def list_patterns(
    pattern_type: str | None = Query(
        None,
        description="Filter by type: time_habit, context_switching, productivity_window, "
                     "recurring_theme, communication_pattern, forgotten_followup, "
                     "work_rhythm, tool_preference"
    ),
    status: str = Query("active", description="Filter by status: active, dismissed, resolved"),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
) -> PatternsListResponse:
    """List detected behavioral patterns.
    
    Returns patterns ordered by frequency (highest first), then last_seen.
    These are LLM-analyzed patterns from conversations and screen activity.
    """
    try:
        # Build query
        query = select(DetectedPattern).where(DetectedPattern.status == status)
        
        if pattern_type:
            query = query.where(DetectedPattern.pattern_type == pattern_type)
        
        query = query.order_by(
            DetectedPattern.frequency.desc(),
            DetectedPattern.last_seen.desc()
        ).limit(limit)
        
        # Execute query
        result = await db.execute(query)
        patterns = result.scalars().all()
        
        # Format response with Why payload
        pattern_list = []
        for p in patterns:
            # Build Why payload for each pattern
            reasons = [
                f"Detected {p.frequency} times",
                f"Pattern type: {p.pattern_type.replace('_', ' ').title()}",
            ]
            if p.suggested_action:
                reasons.append("Suggested action available")
            
            # Confidence based on frequency (rough heuristic)
            confidence = min(0.5 + (p.frequency * 0.05), 0.95)
            
            why = build_why_from_pattern(
                pattern_id=p.id,
                pattern_description=p.description,
                pattern_last_seen=p.last_seen,
                reasons=reasons,
                confidence=confidence,
                source_conversation_ids=p.conversation_ids
            )
            
            pattern_list.append(
                PatternResponse(
                    id=p.id,
                    pattern_type=p.pattern_type,
                    pattern_key=p.pattern_key,
                    description=p.description,
                    frequency=p.frequency,
                    first_seen=p.first_seen.isoformat(),
                    last_seen=p.last_seen.isoformat(),
                    suggested_action=p.suggested_action,
                    conversation_ids=p.conversation_ids,
                    detected_at=p.detected_at.isoformat(),
                    status=p.status,
                    why=why,
                )
            )
        
        # Calculate by_type counts
        by_type: dict[str, int] = {}
        for p in pattern_list:
            by_type[p.pattern_type] = by_type.get(p.pattern_type, 0) + 1
        
        logger.info("patterns_listed", count=len(pattern_list), status=status)
        
        return PatternsListResponse(
            patterns=pattern_list,
            total=len(pattern_list),
            by_type=by_type,
        )
        
    except Exception as e:
        logger.error("patterns_list_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list patterns")


@router.post("/detect", response_model=DetectionResponse)
async def trigger_detection(
    background: bool = Query(False, description="Run detection in background"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> DetectionResponse:
    """Trigger LLM-based behavioral pattern detection.
    
    Analyzes recent conversations and screen captures using Claude
    to identify real behavioral patterns. Replaces old active patterns
    with newly detected ones.
    
    Set background=true to run asynchronously.
    """
    from jarvis_server.patterns.llm_detector import run_detection
    
    if background:
        background_tasks.add_task(_run_detection_background)
        return DetectionResponse(
            status="started",
            message="Pattern detection started in background. Check /patterns for results.",
        )
    
    try:
        logger.info("Starting synchronous pattern detection...")
        patterns = await run_detection()
        return DetectionResponse(
            status="completed",
            message=f"Detected {len(patterns)} behavioral patterns.",
            patterns_found=len(patterns),
        )
    except Exception as e:
        logger.error("pattern_detection_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Pattern detection failed: {str(e)}")


async def _run_detection_background():
    """Background task wrapper for pattern detection."""
    try:
        from jarvis_server.patterns.llm_detector import run_detection
        await run_detection()
    except Exception as e:
        logger.error("background_pattern_detection_failed", error=str(e))


@router.delete("/purge")
async def purge_garbage_patterns(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Purge all dismissed/garbage patterns from the database.
    
    Removes all patterns with status='dismissed' to clean up old
    keyword-counting garbage data.
    """
    try:
        result = await db.execute(
            select(func.count(DetectedPattern.id)).where(
                DetectedPattern.status == "dismissed"
            )
        )
        count = result.scalar() or 0
        
        await db.execute(
            select(DetectedPattern).where(DetectedPattern.status == "dismissed")
        )
        result = await db.execute(
            select(DetectedPattern).where(DetectedPattern.status == "dismissed")
        )
        dismissed = result.scalars().all()
        for p in dismissed:
            await db.delete(p)
        
        await db.commit()
        
        logger.info("purged_dismissed_patterns", count=count)
        return {"status": "purged", "deleted_count": count}
        
    except Exception as e:
        logger.error("purge_failed", error=str(e))
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to purge patterns")


@router.patch("/{pattern_id}/status")
async def update_pattern_status(
    pattern_id: str,
    status: str = Query(..., description="New status: active, dismissed, resolved"),
    db: AsyncSession = Depends(get_db),
) -> PatternResponse:
    """Update pattern status."""
    try:
        if status not in ("active", "dismissed", "resolved"):
            raise HTTPException(
                status_code=400,
                detail="Invalid status. Must be: active, dismissed, or resolved"
            )
        
        result = await db.execute(
            select(DetectedPattern).where(DetectedPattern.id == pattern_id)
        )
        pattern = result.scalar_one_or_none()
        
        if not pattern:
            raise HTTPException(status_code=404, detail="Pattern not found")
        
        pattern.status = status
        
        await db.commit()
        await db.refresh(pattern)
        
        logger.info("pattern_status_updated", id=pattern_id, new_status=status)
        
        # Build Why payload
        reasons = [
            f"Detected {pattern.frequency} times",
            f"Pattern type: {pattern.pattern_type.replace('_', ' ').title()}",
        ]
        if pattern.suggested_action:
            reasons.append("Suggested action available")
        
        confidence = min(0.5 + (pattern.frequency * 0.05), 0.95)
        
        why = build_why_from_pattern(
            pattern_id=pattern.id,
            pattern_description=pattern.description,
            pattern_last_seen=pattern.last_seen,
            reasons=reasons,
            confidence=confidence,
            source_conversation_ids=pattern.conversation_ids
        )
        
        return PatternResponse(
            id=pattern.id,
            pattern_type=pattern.pattern_type,
            pattern_key=pattern.pattern_key,
            description=pattern.description,
            frequency=pattern.frequency,
            first_seen=pattern.first_seen.isoformat(),
            last_seen=pattern.last_seen.isoformat(),
            suggested_action=pattern.suggested_action,
            conversation_ids=pattern.conversation_ids,
            detected_at=pattern.detected_at.isoformat(),
            status=pattern.status,
            why=why,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("pattern_status_update_failed", error=str(e), id=pattern_id)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update pattern status")


@router.delete("/{pattern_id}")
async def delete_pattern(
    pattern_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a detected pattern."""
    try:
        result = await db.execute(
            select(DetectedPattern).where(DetectedPattern.id == pattern_id)
        )
        pattern = result.scalar_one_or_none()
        
        if not pattern:
            raise HTTPException(status_code=404, detail="Pattern not found")
        
        await db.delete(pattern)
        await db.commit()
        
        logger.info("pattern_deleted", id=pattern_id)
        
        return {"status": "deleted", "id": pattern_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("pattern_delete_failed", error=str(e), id=pattern_id)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete pattern")
