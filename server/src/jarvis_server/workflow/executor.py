"""Workflow execution engine for running approved automations."""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.db.models import WorkflowExecution
from jarvis_server.workflow.repository import PatternRepository
from jarvis_server.workflow.actions import ActionResult, get_handler
from jarvis_server.workflow.safety import SafetyClassifier
from jarvis_server.workflow.undo import UndoManager

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of executing a workflow."""
    success: bool
    execution_id: str
    actions_completed: int
    actions_failed: int
    results: list[ActionResult]
    error: Optional[str] = None


class WorkflowExecutor:
    """Executes workflow automations."""

    UNDO_WINDOW_HOURS = 24
    MAX_EXECUTIONS_PER_HOUR = 60

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PatternRepository(session)

    async def execute_workflow(
        self,
        pattern_id: str,
        trigger_capture_id: Optional[str] = None,
        user_approved: bool = False,
    ) -> ExecutionResult:
        """Execute a workflow pattern."""
        pattern = await self.repo.get_pattern(pattern_id)
        if not pattern:
            return ExecutionResult(
                success=False, execution_id="", actions_completed=0,
                actions_failed=0, results=[], error="Pattern not found",
            )

        if not pattern.is_active:
            return ExecutionResult(
                success=False, execution_id="", actions_completed=0,
                actions_failed=0, results=[], error="Pattern is suspended",
            )

        if pattern.trust_tier == "observe":
            return ExecutionResult(
                success=False, execution_id="", actions_completed=0,
                actions_failed=0, results=[],
                error="Pattern is in observe tier - cannot execute",
            )

        if pattern.trust_tier == "suggest" and not user_approved:
            return ExecutionResult(
                success=False, execution_id="", actions_completed=0,
                actions_failed=0, results=[],
                error="Pattern requires user approval",
            )

        try:
            actions = json.loads(pattern.actions)
        except json.JSONDecodeError:
            return ExecutionResult(
                success=False, execution_id="", actions_completed=0,
                actions_failed=0, results=[], error="Invalid actions JSON",
            )

        # Check for destructive actions without approval
        for action in actions:
            if SafetyClassifier.is_destructive(action) and not user_approved:
                return ExecutionResult(
                    success=False, execution_id="", actions_completed=0,
                    actions_failed=0, results=[],
                    error="Destructive actions require explicit approval",
                )

        # Validate all actions before executing any
        for action in actions:
            action_type = action.get("type", "").lower()
            handler = get_handler(action_type)
            if handler and not handler.validate(action):
                return ExecutionResult(
                    success=False, execution_id="", actions_completed=0,
                    actions_failed=0, results=[],
                    error=f"Action validation failed: {action_type}",
                )

        # Create execution record
        execution = await self.repo.record_execution(
            pattern_id=pattern_id,
            trigger_capture_id=trigger_capture_id,
            user_approved=user_approved,
        )

        await self.repo.update_execution(
            execution.id,
            status="running",
            started_at=datetime.now(timezone.utc),
        )

        # Execute each action
        results = []
        actions_completed = 0
        actions_failed = 0
        all_undo_states = []

        for action in actions:
            try:
                result = await self._execute_action(action)
                results.append(result)

                if result.success:
                    actions_completed += 1
                    if result.undo_state:
                        all_undo_states.append(result.undo_state)
                else:
                    actions_failed += 1

            except Exception as e:
                logger.error(f"Action execution error: {e}")
                results.append(ActionResult(
                    success=False,
                    action_type=action.get("type", "unknown"),
                    message=str(e),
                ))
                actions_failed += 1

        final_status = "completed" if actions_failed == 0 else "failed"
        undo_until = datetime.now(timezone.utc) + timedelta(hours=self.UNDO_WINDOW_HOURS)

        await self.repo.update_execution(
            execution.id,
            status=final_status,
            completed_at=datetime.now(timezone.utc),
            result=json.dumps({"actions": [r.__dict__ for r in results]}),
            undo_available_until=undo_until if all_undo_states else None,
            undo_state=json.dumps(all_undo_states) if all_undo_states else None,
        )

        return ExecutionResult(
            success=actions_failed == 0,
            execution_id=execution.id,
            actions_completed=actions_completed,
            actions_failed=actions_failed,
            results=results,
        )

    async def _execute_action(self, action: dict) -> ActionResult:
        """Execute a single action using the handler registry."""
        action_type = action.get("type", "").lower()
        handler = get_handler(action_type)

        if not handler:
            return ActionResult(
                success=False,
                action_type=action_type,
                message=f"Unsupported action type: {action_type}",
            )

        return await handler.execute(action)

    async def undo_execution(self, execution_id: str) -> bool:
        """Undo an execution if within the undo window."""
        manager = UndoManager(self.session)
        result = await manager.undo(execution_id)
        return result.success
