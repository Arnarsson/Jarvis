"""Workflow automation API endpoints."""

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.db.models import WorkflowExecution
from jarvis_server.db.session import get_db
from jarvis_server.workflow.repository import PatternRepository
from jarvis_server.workflow.detector import PatternDetector
from jarvis_server.workflow.executor import WorkflowExecutor
from jarvis_server.workflow.false_positive import FalsePositiveTracker
from jarvis_server.workflow.safety import SafetyClassifier
from jarvis_server.workflow.undo import UndoManager


router = APIRouter(prefix="/api/workflow", tags=["workflow"])


# ============================================================================
# Request/Response Models
# ============================================================================


class PatternResponse(BaseModel):
    """Pattern response model."""
    id: str
    name: str
    description: Optional[str]
    pattern_type: str
    trust_tier: str
    is_active: bool
    frequency_count: int
    last_seen: Optional[datetime]
    accuracy: float
    total_executions: int
    created_at: datetime


class PatternListResponse(BaseModel):
    """List of patterns."""
    patterns: list[PatternResponse]
    total: int


class SuggestionResponse(BaseModel):
    """Automation suggestion response."""
    id: str
    name: str
    description: str
    pattern_type: str
    trigger_description: str
    action_description: str
    confidence: float
    similar_captures: list[str]


class SuggestionListResponse(BaseModel):
    """List of suggestions."""
    suggestions: list[SuggestionResponse]
    total: int


class PatternUpdateRequest(BaseModel):
    """Request to update a pattern."""
    name: Optional[str] = None
    description: Optional[str] = None
    trust_tier: Optional[str] = None


class FeedbackRequest(BaseModel):
    """Request to provide feedback on execution."""
    was_correct: bool


class ExecuteRequest(BaseModel):
    """Request to manually trigger a workflow execution."""
    trigger_capture_id: Optional[str] = None
    user_approved: bool = True


class ExecutionResponse(BaseModel):
    """Single execution response."""
    id: str
    pattern_id: str
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    user_approved: bool
    undo_available_until: Optional[datetime]
    was_correct: Optional[bool]
    actions_result: Optional[dict]
    created_at: datetime


class ExecutionListResponse(BaseModel):
    """List of executions."""
    executions: list[ExecutionResponse]
    total: int


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/patterns", response_model=PatternListResponse)
async def list_patterns(
    trust_tier: Optional[str] = None,
    active_only: bool = True,
    limit: int = 50,
    session: AsyncSession = Depends(get_db),
):
    """List all workflow patterns."""
    repo = PatternRepository(session)
    patterns = await repo.list_patterns(
        trust_tier=trust_tier,
        active_only=active_only,
        limit=limit,
    )
    
    responses = []
    for p in patterns:
        stats = await repo.get_pattern_stats(p.id)
        responses.append(PatternResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            pattern_type=p.pattern_type,
            trust_tier=p.trust_tier,
            is_active=p.is_active,
            frequency_count=p.frequency_count,
            last_seen=p.last_seen,
            accuracy=stats.get("accuracy", 0.0),
            total_executions=stats.get("total_executions", 0),
            created_at=p.created_at,
        ))
    
    return PatternListResponse(patterns=responses, total=len(responses))


@router.get("/patterns/{pattern_id}")
async def get_pattern(
    pattern_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Get a specific pattern."""
    repo = PatternRepository(session)
    pattern = await repo.get_pattern(pattern_id)
    
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")
    
    stats = await repo.get_pattern_stats(pattern_id)
    
    return {
        "id": pattern.id,
        "name": pattern.name,
        "description": pattern.description,
        "pattern_type": pattern.pattern_type,
        "trust_tier": pattern.trust_tier,
        "is_active": pattern.is_active,
        "frequency_count": pattern.frequency_count,
        "last_seen": pattern.last_seen,
        "trigger_conditions": pattern.trigger_conditions,
        "actions": pattern.actions,
        "stats": stats,
        "created_at": pattern.created_at,
        "updated_at": pattern.updated_at,
    }


@router.patch("/patterns/{pattern_id}")
async def update_pattern(
    pattern_id: str,
    request: PatternUpdateRequest,
    session: AsyncSession = Depends(get_db),
):
    """Update a pattern."""
    repo = PatternRepository(session)
    
    updates = request.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")
    
    # Validate trust_tier if provided
    if "trust_tier" in updates and updates["trust_tier"] not in ["observe", "suggest", "auto"]:
        raise HTTPException(status_code=400, detail="Invalid trust tier")
    
    pattern = await repo.update_pattern(pattern_id, **updates)
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")
    
    return {"status": "updated", "pattern_id": pattern_id}


@router.post("/patterns/{pattern_id}/promote")
async def promote_pattern(
    pattern_id: str,
    tier: str,
    session: AsyncSession = Depends(get_db),
):
    """Promote a pattern to a new trust tier."""
    if tier not in ["observe", "suggest", "auto"]:
        raise HTTPException(status_code=400, detail="Invalid trust tier")
    
    repo = PatternRepository(session)
    pattern = await repo.promote_tier(pattern_id, tier)
    
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")
    
    return {"status": "promoted", "pattern_id": pattern_id, "new_tier": tier}


@router.post("/patterns/{pattern_id}/suspend")
async def suspend_pattern(
    pattern_id: str,
    reason: str = "Manual suspension",
    session: AsyncSession = Depends(get_db),
):
    """Suspend a pattern."""
    repo = PatternRepository(session)
    pattern = await repo.suspend_pattern(pattern_id, reason)
    
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")
    
    return {"status": "suspended", "pattern_id": pattern_id}


@router.post("/patterns/{pattern_id}/unsuspend")
async def unsuspend_pattern(
    pattern_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Reactivate a suspended pattern."""
    repo = PatternRepository(session)
    pattern = await repo.unsuspend_pattern(pattern_id)
    
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")
    
    return {"status": "unsuspended", "pattern_id": pattern_id}


@router.get("/suggestions", response_model=SuggestionListResponse)
async def list_suggestions(
    session: AsyncSession = Depends(get_db),
):
    """List pending automation suggestions (patterns in observe tier with high frequency)."""
    repo = PatternRepository(session)
    
    # Get patterns in observe tier that have been seen enough times
    patterns = await repo.list_patterns(trust_tier="observe", active_only=True)
    
    suggestions = []
    for p in patterns:
        if p.frequency_count >= 3:  # Minimum frequency for suggestion
            suggestions.append(SuggestionResponse(
                id=p.id,
                name=p.name,
                description=p.description or "",
                pattern_type=p.pattern_type,
                trigger_description=f"When Jarvis detects this pattern (seen {p.frequency_count} times)",
                action_description="Jarvis will notify you",
                confidence=min(p.frequency_count / 10, 0.9),
                similar_captures=[],  # TODO: Add capture references
            ))
    
    return SuggestionListResponse(suggestions=suggestions, total=len(suggestions))


@router.post("/suggestions/{pattern_id}/approve")
async def approve_suggestion(
    pattern_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Approve a suggestion - promote to suggest tier."""
    repo = PatternRepository(session)
    pattern = await repo.promote_tier(pattern_id, "suggest")
    
    if not pattern:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    
    return {"status": "approved", "pattern_id": pattern_id, "new_tier": "suggest"}


@router.post("/suggestions/{pattern_id}/reject")
async def reject_suggestion(
    pattern_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Reject a suggestion - suspend the pattern."""
    repo = PatternRepository(session)
    pattern = await repo.suspend_pattern(pattern_id, "Rejected by user")
    
    if not pattern:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    
    return {"status": "rejected", "pattern_id": pattern_id}


@router.get("/analyze")
async def analyze_patterns(
    hours: int = 24,
    session: AsyncSession = Depends(get_db),
):
    """Analyze recent captures for pattern candidates."""
    detector = PatternDetector(session)
    candidates = await detector.analyze_recent(hours=hours)
    
    return {
        "analyzed_hours": hours,
        "candidates_found": len(candidates),
        "candidates": candidates[:20],  # Limit response size
    }


@router.post("/executions/{execution_id}/feedback")
async def provide_feedback(
    execution_id: str,
    request: FeedbackRequest,
    session: AsyncSession = Depends(get_db),
):
    """Provide feedback on an execution. Auto-suspends pattern if accuracy drops below 80%."""
    tracker = FalsePositiveTracker(session)
    result = await tracker.record_feedback(execution_id, request.was_correct)

    return {
        "status": result["status"],
        "execution_id": execution_id,
        "was_correct": request.was_correct,
        "suspension": result.get("suspension"),
    }


@router.get("/patterns/{pattern_id}/accuracy")
async def get_pattern_accuracy(
    pattern_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Get accuracy stats for a pattern over the last 10 reviewed executions."""
    repo = PatternRepository(session)
    pattern = await repo.get_pattern(pattern_id)
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")

    tracker = FalsePositiveTracker(session)
    return await tracker.get_accuracy(pattern_id)


@router.get("/patterns/{pattern_id}/safety")
async def get_pattern_safety(
    pattern_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Get safety classification report for a pattern's actions."""
    repo = PatternRepository(session)
    pattern = await repo.get_pattern(pattern_id)
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")

    import json as _json
    try:
        actions = _json.loads(pattern.actions)
    except (ValueError, TypeError):
        actions = []

    return {
        "pattern_id": pattern_id,
        "overall_safety": SafetyClassifier.classify_all(actions).value,
        "actions": SafetyClassifier.get_report(actions),
    }


@router.get("/executions/{execution_id}/can-undo")
async def check_can_undo(
    execution_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Check if an execution can still be undone."""
    manager = UndoManager(session)
    can = await manager.can_undo(execution_id)
    deadline = await manager.get_undo_deadline(execution_id)

    return {
        "execution_id": execution_id,
        "can_undo": can,
        "undo_deadline": deadline,
    }


# ============================================================================
# Execution Endpoints
# ============================================================================


@router.post("/execute/{pattern_id}")
async def execute_workflow(
    pattern_id: str,
    request: ExecuteRequest = ExecuteRequest(),
    session: AsyncSession = Depends(get_db),
):
    """Manually trigger execution of a workflow pattern."""
    executor = WorkflowExecutor(session)
    result = await executor.execute_workflow(
        pattern_id=pattern_id,
        trigger_capture_id=request.trigger_capture_id,
        user_approved=request.user_approved,
    )

    if not result.success and not result.execution_id:
        raise HTTPException(status_code=400, detail=result.error)

    return {
        "status": "completed" if result.success else "failed",
        "execution_id": result.execution_id,
        "actions_completed": result.actions_completed,
        "actions_failed": result.actions_failed,
        "error": result.error,
    }


@router.get("/executions", response_model=ExecutionListResponse)
async def list_executions(
    pattern_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_db),
):
    """List recent workflow executions."""
    query = select(WorkflowExecution)

    if pattern_id:
        query = query.where(WorkflowExecution.pattern_id == pattern_id)
    if status:
        query = query.where(WorkflowExecution.status == status)

    query = query.order_by(WorkflowExecution.created_at.desc()).limit(limit)
    result = await session.execute(query)
    executions = list(result.scalars().all())

    responses = []
    for ex in executions:
        actions_result = None
        if ex.result:
            try:
                actions_result = json.loads(ex.result)
            except (json.JSONDecodeError, TypeError):
                actions_result = None

        responses.append(ExecutionResponse(
            id=ex.id,
            pattern_id=ex.pattern_id,
            status=ex.status,
            started_at=ex.started_at,
            completed_at=ex.completed_at,
            user_approved=ex.user_approved,
            undo_available_until=ex.undo_available_until,
            was_correct=ex.was_correct,
            actions_result=actions_result,
            created_at=ex.created_at,
        ))

    return ExecutionListResponse(executions=responses, total=len(responses))


@router.get("/executions/{execution_id}")
async def get_execution(
    execution_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Get details of a specific execution."""
    result = await session.execute(
        select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
    )
    execution = result.scalar_one_or_none()

    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")

    actions_result = None
    if execution.result:
        try:
            actions_result = json.loads(execution.result)
        except (json.JSONDecodeError, TypeError):
            actions_result = None

    undo_state = None
    if execution.undo_state:
        try:
            undo_state = json.loads(execution.undo_state)
        except (json.JSONDecodeError, TypeError):
            undo_state = None

    return {
        "id": execution.id,
        "pattern_id": execution.pattern_id,
        "trigger_capture_id": execution.trigger_capture_id,
        "status": execution.status,
        "started_at": execution.started_at,
        "completed_at": execution.completed_at,
        "user_approved": execution.user_approved,
        "undo_available_until": execution.undo_available_until,
        "was_correct": execution.was_correct,
        "actions_result": actions_result,
        "undo_state": undo_state,
        "error_message": execution.error_message,
        "created_at": execution.created_at,
    }


@router.post("/executions/{execution_id}/undo")
async def undo_execution(
    execution_id: str,
    session: AsyncSession = Depends(get_db),
):
    """Undo an execution if within the 24-hour undo window."""
    executor = WorkflowExecutor(session)
    success = await executor.undo_execution(execution_id)

    if not success:
        raise HTTPException(
            status_code=400,
            detail="Cannot undo: execution not found, already undone, or undo window expired",
        )

    return {"status": "undone", "execution_id": execution_id}
