"""False positive tracking and auto-suspension for workflow patterns.

Monitors execution accuracy and automatically suspends patterns
that fall below the accuracy threshold.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.db.models import WorkflowExecution, Pattern
from jarvis_server.workflow.repository import PatternRepository

logger = logging.getLogger(__name__)

ACCURACY_THRESHOLD = 0.80  # 80%
REVIEW_WINDOW = 10  # last N executions with feedback


class FalsePositiveTracker:
    """Tracks execution accuracy and auto-suspends unreliable patterns."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PatternRepository(session)

    async def record_feedback(self, execution_id: str, was_correct: bool) -> dict:
        """Record feedback and check if pattern should be suspended.

        Returns dict with feedback status and any suspension action taken.
        """
        await self.repo.record_feedback(execution_id, was_correct)

        # Get the pattern for this execution
        result = await self.session.execute(
            select(WorkflowExecution.pattern_id).where(
                WorkflowExecution.id == execution_id
            )
        )
        row = result.first()
        if not row:
            return {"status": "recorded", "suspension": None}

        pattern_id = row[0]
        should_suspend = await self.check_suspension(pattern_id)

        if should_suspend:
            await self.repo.suspend_pattern(
                pattern_id,
                reason=f"Auto-suspended: accuracy below {ACCURACY_THRESHOLD:.0%} over last {REVIEW_WINDOW} executions",
            )
            logger.warning(f"Pattern {pattern_id} auto-suspended for low accuracy")
            return {"status": "recorded", "suspension": "auto_suspended"}

        return {"status": "recorded", "suspension": None}

    async def get_accuracy(self, pattern_id: str) -> dict:
        """Get accuracy stats for a pattern over the review window."""
        result = await self.session.execute(
            select(WorkflowExecution)
            .where(
                WorkflowExecution.pattern_id == pattern_id,
                WorkflowExecution.was_correct.isnot(None),
            )
            .order_by(WorkflowExecution.created_at.desc())
            .limit(REVIEW_WINDOW)
        )
        executions = list(result.scalars().all())

        if not executions:
            return {
                "pattern_id": pattern_id,
                "total_reviewed": 0,
                "correct": 0,
                "incorrect": 0,
                "accuracy": None,
                "threshold": ACCURACY_THRESHOLD,
                "at_risk": False,
            }

        correct = sum(1 for e in executions if e.was_correct)
        total = len(executions)
        accuracy = correct / total if total > 0 else 0.0

        return {
            "pattern_id": pattern_id,
            "total_reviewed": total,
            "correct": correct,
            "incorrect": total - correct,
            "accuracy": accuracy,
            "threshold": ACCURACY_THRESHOLD,
            "at_risk": total >= 3 and accuracy < ACCURACY_THRESHOLD,
        }

    async def check_suspension(self, pattern_id: str) -> bool:
        """Check if a pattern should be suspended due to low accuracy.

        Only triggers after at least REVIEW_WINDOW executions have feedback.
        """
        stats = await self.get_accuracy(pattern_id)

        if stats["total_reviewed"] < REVIEW_WINDOW:
            return False

        return stats["accuracy"] < ACCURACY_THRESHOLD
