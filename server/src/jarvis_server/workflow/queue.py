"""ARQ tasks for workflow execution and maintenance."""

import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func

from jarvis_server.db.session import AsyncSessionLocal
from jarvis_server.db.models import WorkflowExecution
from jarvis_server.workflow.executor import WorkflowExecutor
from jarvis_server.workflow.undo import UndoManager

logger = logging.getLogger(__name__)

MAX_EXECUTIONS_PER_HOUR = 60


async def execute_workflow_task(
    ctx: dict,
    pattern_id: str,
    trigger_capture_id: str | None = None,
    user_approved: bool = False,
) -> dict:
    """ARQ task: execute a workflow pattern.

    Respects rate limits and handles retries via ARQ's built-in backoff.
    """
    async with AsyncSessionLocal() as session:
        # Rate limit check
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        result = await session.execute(
            select(func.count(WorkflowExecution.id)).where(
                WorkflowExecution.created_at >= one_hour_ago,
            )
        )
        recent_count = result.scalar() or 0

        if recent_count >= MAX_EXECUTIONS_PER_HOUR:
            logger.warning(
                f"Rate limit hit: {recent_count} executions in last hour, skipping {pattern_id}"
            )
            return {
                "status": "rate_limited",
                "pattern_id": pattern_id,
                "recent_executions": recent_count,
            }

        executor = WorkflowExecutor(session)
        exec_result = await executor.execute_workflow(
            pattern_id=pattern_id,
            trigger_capture_id=trigger_capture_id,
            user_approved=user_approved,
        )

    logger.info(
        f"Workflow execution: pattern={pattern_id} success={exec_result.success} "
        f"completed={exec_result.actions_completed} failed={exec_result.actions_failed}"
    )
    return {
        "status": "completed" if exec_result.success else "failed",
        "execution_id": exec_result.execution_id,
        "pattern_id": pattern_id,
        "actions_completed": exec_result.actions_completed,
        "actions_failed": exec_result.actions_failed,
        "error": exec_result.error,
    }


async def cleanup_expired_undos(ctx: dict) -> dict:
    """ARQ cron task: clear undo state for expired executions."""
    async with AsyncSessionLocal() as session:
        manager = UndoManager(session)
        cleaned = await manager.cleanup_expired()

    logger.info(f"Undo cleanup: {cleaned} expired entries cleared")
    return {"cleaned": cleaned}
