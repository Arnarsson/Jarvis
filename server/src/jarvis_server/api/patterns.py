"""Actionable Patterns API.

Provides endpoints to list detected (conversation-derived) behavioral patterns and
perform fixed actions on them:
- Convert to Automation (creates a workflow automation draft)
- Convert to Project (creates a lightweight project record)
- Ignore / Snooze (dismisses the pattern)

This is part of the "Super Feedback" pivot: patterns must never be read-only.

Contract (v1):
- GET  /api/patterns
- POST /api/patterns/{id}/convert-automation
- POST /api/patterns/{id}/convert-project
- POST /api/patterns/{id}/dismiss

Backward compatibility:
- GET /api/v2/patterns still exists with the old schema for older clients.
"""

from __future__ import annotations

import json

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.api.helpers import build_why_from_pattern
from jarvis_server.api.models import WhyPayload
from jarvis_server.db.models import DetectedPattern, Pattern as WorkflowPattern, Project
from jarvis_server.db.session import get_db

logger = structlog.get_logger(__name__)

# New actionable API (requested contract)
router = APIRouter(prefix="/api/patterns", tags=["patterns"])

# Legacy read-only API (keep until dashboard migration is complete)
legacy_router = APIRouter(prefix="/api/v2/patterns", tags=["patterns"])


# ────────────────────────────────────────────────────────────────
# Models (new actionable schema)
# ────────────────────────────────────────────────────────────────


class PatternAction(BaseModel):
    label: str
    action: str
    params: dict = Field(default_factory=dict)


class ActionablePattern(BaseModel):
    id: str
    type: str
    title: str
    description: str
    frequency: str
    confidence: float
    detected_at: str
    occurrence_count: int
    actions: list[PatternAction]
    why: WhyPayload | None = None


class ActionablePatternsResponse(BaseModel):
    patterns: list[ActionablePattern]


class ConvertAutomationResponse(BaseModel):
    status: str
    pattern_id: str
    automation_draft_id: str


class ConvertProjectResponse(BaseModel):
    status: str
    pattern_id: str
    project_id: str


class DismissResponse(BaseModel):
    status: str
    pattern_id: str
    snooze_days: int


def _frequency_label(p: DetectedPattern) -> str:
    # Conversation patterns are not strictly time-based; expose a friendly label.
    if p.frequency >= 20:
        return "very frequent"
    if p.frequency >= 10:
        return "frequent"
    if p.frequency >= 5:
        return "recurring"
    return "occasional"


def _confidence_for_pattern(p: DetectedPattern) -> float:
    # Rough heuristic: higher frequency -> higher confidence.
    return float(min(0.5 + (p.frequency * 0.05), 0.95))


def _default_actions(p: DetectedPattern) -> list[PatternAction]:
    """Fixed 2-3 actions for every pattern card."""
    return [
        PatternAction(
            label="Convert to Automation",
            action="create_automation",
            params={
                # Hints for draft generation
                "pattern_type": p.pattern_type,
                "pattern_key": p.pattern_key,
            },
        ),
        PatternAction(
            label="Create Project",
            action="create_project",
            params={
                "name": p.pattern_key,
            },
        ),
        PatternAction(
            label="Ignore",
            action="dismiss",
            params={
                "snooze_days": 30,
            },
        ),
    ]


@router.get("", response_model=ActionablePatternsResponse)
async def list_actionable_patterns(
    pattern_type: str | None = Query(None, description="Filter by detected pattern type"),
    status: str = Query("active", description="Filter by status: active, dismissed, resolved"),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
) -> ActionablePatternsResponse:
    """List detected patterns with fixed actions (Convert/Project/Ignore) and Why payload."""
    try:
        query = select(DetectedPattern).where(DetectedPattern.status == status)
        if pattern_type:
            query = query.where(DetectedPattern.pattern_type == pattern_type)

        query = query.order_by(DetectedPattern.frequency.desc(), DetectedPattern.last_seen.desc()).limit(limit)

        result = await db.execute(query)
        patterns = result.scalars().all()

        out: list[ActionablePattern] = []
        for p in patterns:
            reasons = [
                f"Detected {p.frequency} times",
                f"Pattern type: {p.pattern_type.replace('_', ' ').title()}",
            ]
            if p.suggested_action:
                reasons.append("Suggested action available")

            confidence = _confidence_for_pattern(p)
            why = build_why_from_pattern(
                pattern_id=p.id,
                pattern_description=p.description,
                pattern_last_seen=p.last_seen,
                reasons=reasons,
                confidence=confidence,
                source_conversation_ids=p.conversation_ids,
            )

            out.append(
                ActionablePattern(
                    id=p.id,
                    type=p.pattern_type,
                    title=p.pattern_key,
                    description=p.description,
                    frequency=_frequency_label(p),
                    confidence=confidence,
                    detected_at=p.detected_at.isoformat(),
                    occurrence_count=p.frequency,
                    actions=_default_actions(p),
                    why=why,
                )
            )

        logger.info("actionable_patterns_listed", count=len(out), status=status)
        return ActionablePatternsResponse(patterns=out)

    except Exception as e:
        logger.error("actionable_patterns_list_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list patterns")


@router.post("/{pattern_id}/convert-automation", response_model=ConvertAutomationResponse)
async def convert_pattern_to_automation(
    pattern_id: str,
    db: AsyncSession = Depends(get_db),
) -> ConvertAutomationResponse:
    """Create a workflow automation *draft* from a detected pattern."""
    try:
        result = await db.execute(select(DetectedPattern).where(DetectedPattern.id == pattern_id))
        p = result.scalar_one_or_none()
        if not p:
            raise HTTPException(status_code=404, detail="Pattern not found")

        # Create a safe, non-active draft automation.
        trigger_conditions = {
            "trigger": "manual",
            "source": "detected_pattern",
            "pattern_type": p.pattern_type,
            "pattern_key": p.pattern_key,
        }
        actions = [
            {
                "type": "notify",
                "params": {
                    "message": f"Automation draft from pattern: {p.pattern_key} ({p.pattern_type}).",
                },
            }
        ]

        draft = WorkflowPattern(
            name=f"Draft: {p.pattern_key}",
            description=p.description,
            pattern_type="REPETITIVE_ACTION",
            trigger_conditions=json.dumps(trigger_conditions),
            actions=json.dumps(actions),
            frequency_count=p.frequency,
            last_seen=p.last_seen,
            trust_tier="suggest",
            is_active=False,
        )
        db.add(draft)

        # Mark pattern resolved (converted)
        p.status = "resolved"

        await db.commit()
        await db.refresh(draft)

        logger.info("pattern_converted_to_automation", pattern_id=pattern_id, draft_id=draft.id)
        return ConvertAutomationResponse(status="created", pattern_id=pattern_id, automation_draft_id=draft.id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("pattern_convert_automation_failed", error=str(e), pattern_id=pattern_id)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to convert pattern to automation")


@router.post("/{pattern_id}/convert-project", response_model=ConvertProjectResponse)
async def convert_pattern_to_project(
    pattern_id: str,
    name: str | None = Query(None, description="Optional project name override"),
    db: AsyncSession = Depends(get_db),
) -> ConvertProjectResponse:
    """Create a lightweight project record from a detected pattern."""
    try:
        result = await db.execute(select(DetectedPattern).where(DetectedPattern.id == pattern_id))
        p = result.scalar_one_or_none()
        if not p:
            raise HTTPException(status_code=404, detail="Pattern not found")

        project = Project(
            name=(name or p.pattern_key)[:200],
            description=p.description,
            source_pattern_id=p.id,
        )
        db.add(project)

        # Mark pattern resolved (converted)
        p.status = "resolved"

        await db.commit()
        await db.refresh(project)

        logger.info("pattern_converted_to_project", pattern_id=pattern_id, project_id=project.id)
        return ConvertProjectResponse(status="created", pattern_id=pattern_id, project_id=project.id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("pattern_convert_project_failed", error=str(e), pattern_id=pattern_id)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to convert pattern to project")


@router.post("/{pattern_id}/dismiss", response_model=DismissResponse)
async def dismiss_pattern(
    pattern_id: str,
    snooze_days: int = Query(30, ge=1, le=365, description="Days to snooze/ignore the pattern"),
    db: AsyncSession = Depends(get_db),
) -> DismissResponse:
    """Dismiss/snooze a detected pattern."""
    try:
        result = await db.execute(select(DetectedPattern).where(DetectedPattern.id == pattern_id))
        p = result.scalar_one_or_none()
        if not p:
            raise HTTPException(status_code=404, detail="Pattern not found")

        p.status = "dismissed"
        await db.commit()

        logger.info("pattern_dismissed", pattern_id=pattern_id, snooze_days=snooze_days)
        return DismissResponse(status="dismissed", pattern_id=pattern_id, snooze_days=snooze_days)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("pattern_dismiss_failed", error=str(e), pattern_id=pattern_id)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to dismiss pattern")


# ────────────────────────────────────────────────────────────────
# Legacy list endpoint (old schema)
# ────────────────────────────────────────────────────────────────


class LegacyPatternResponse(BaseModel):
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


class LegacyPatternsListResponse(BaseModel):
    patterns: list[LegacyPatternResponse]
    total: int
    by_type: dict[str, int]


class DetectionResponse(BaseModel):
    status: str
    message: str
    patterns_found: int | None = None


@legacy_router.get("", response_model=LegacyPatternsListResponse)
async def list_patterns_legacy(
    pattern_type: str | None = Query(None),
    status: str = Query("active"),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
) -> LegacyPatternsListResponse:
    """Legacy list endpoint kept for older clients."""
    try:
        query = select(DetectedPattern).where(DetectedPattern.status == status)
        if pattern_type:
            query = query.where(DetectedPattern.pattern_type == pattern_type)
        query = query.order_by(DetectedPattern.frequency.desc(), DetectedPattern.last_seen.desc()).limit(limit)

        result = await db.execute(query)
        patterns = result.scalars().all()

        pattern_list: list[LegacyPatternResponse] = []
        for p in patterns:
            reasons = [
                f"Detected {p.frequency} times",
                f"Pattern type: {p.pattern_type.replace('_', ' ').title()}",
            ]
            if p.suggested_action:
                reasons.append("Suggested action available")

            confidence = _confidence_for_pattern(p)
            why = build_why_from_pattern(
                pattern_id=p.id,
                pattern_description=p.description,
                pattern_last_seen=p.last_seen,
                reasons=reasons,
                confidence=confidence,
                source_conversation_ids=p.conversation_ids,
            )

            pattern_list.append(
                LegacyPatternResponse(
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

        by_type: dict[str, int] = {}
        for p in pattern_list:
            by_type[p.pattern_type] = by_type.get(p.pattern_type, 0) + 1

        return LegacyPatternsListResponse(patterns=pattern_list, total=len(pattern_list), by_type=by_type)

    except Exception as e:
        logger.error("patterns_list_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list patterns")


@legacy_router.post("/detect", response_model=DetectionResponse)
async def trigger_detection(
    background: bool = Query(False, description="Run detection in background"),
    background_tasks: BackgroundTasks = BackgroundTasks(),
) -> DetectionResponse:
    """Trigger LLM-based behavioral pattern detection (legacy path)."""
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
    try:
        from jarvis_server.patterns.llm_detector import run_detection

        await run_detection()
    except Exception as e:
        logger.error("background_pattern_detection_failed", error=str(e))


@legacy_router.delete("/purge")
async def purge_garbage_patterns(db: AsyncSession = Depends(get_db)) -> dict:
    """Purge all dismissed patterns from the database."""
    try:
        result = await db.execute(select(func.count(DetectedPattern.id)).where(DetectedPattern.status == "dismissed"))
        count = result.scalar() or 0

        result = await db.execute(select(DetectedPattern).where(DetectedPattern.status == "dismissed"))
        dismissed = result.scalars().all()
        for p in dismissed:
            await db.delete(p)

        await db.commit()
        return {"status": "purged", "deleted_count": count}

    except Exception as e:
        logger.error("purge_failed", error=str(e))
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to purge patterns")


@legacy_router.patch("/{pattern_id}/status")
async def update_pattern_status_legacy(
    pattern_id: str,
    status: str = Query(..., description="New status: active, dismissed, resolved"),
    db: AsyncSession = Depends(get_db),
) -> LegacyPatternResponse:
    """Legacy status update endpoint."""
    try:
        if status not in ("active", "dismissed", "resolved"):
            raise HTTPException(status_code=400, detail="Invalid status. Must be: active, dismissed, or resolved")

        result = await db.execute(select(DetectedPattern).where(DetectedPattern.id == pattern_id))
        pattern = result.scalar_one_or_none()
        if not pattern:
            raise HTTPException(status_code=404, detail="Pattern not found")

        pattern.status = status
        await db.commit()
        await db.refresh(pattern)

        reasons = [
            f"Detected {pattern.frequency} times",
            f"Pattern type: {pattern.pattern_type.replace('_', ' ').title()}",
        ]
        if pattern.suggested_action:
            reasons.append("Suggested action available")

        confidence = _confidence_for_pattern(pattern)
        why = build_why_from_pattern(
            pattern_id=pattern.id,
            pattern_description=pattern.description,
            pattern_last_seen=pattern.last_seen,
            reasons=reasons,
            confidence=confidence,
            source_conversation_ids=pattern.conversation_ids,
        )

        return LegacyPatternResponse(
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


@legacy_router.delete("/{pattern_id}")
async def delete_pattern_legacy(pattern_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Legacy delete endpoint."""
    try:
        result = await db.execute(select(DetectedPattern).where(DetectedPattern.id == pattern_id))
        pattern = result.scalar_one_or_none()
        if not pattern:
            raise HTTPException(status_code=404, detail="Pattern not found")

        await db.delete(pattern)
        await db.commit()
        return {"status": "deleted", "id": pattern_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("pattern_delete_failed", error=str(e), id=pattern_id)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete pattern")
