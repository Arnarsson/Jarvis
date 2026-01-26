"""Undo manager for reversing workflow executions.

Provides a clean interface for checking undo eligibility, executing undos,
and cleaning up expired undo state.
"""

import json
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.db.models import WorkflowExecution
from jarvis_server.workflow.actions import get_handler
from jarvis_server.workflow.repository import PatternRepository

logger = logging.getLogger(__name__)

UNDO_WINDOW_HOURS = 24


class UndoResult:
    """Result of an undo operation."""

    def __init__(self, success: bool, execution_id: str, message: str):
        self.success = success
        self.execution_id = execution_id
        self.message = message


class UndoManager:
    """Manages undo operations for workflow executions."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = PatternRepository(session)

    async def can_undo(self, execution_id: str) -> bool:
        """Check if an execution can be undone."""
        execution = await self._get_execution(execution_id)
        if not execution:
            return False
        if execution.status == "undone":
            return False
        if not execution.undo_available_until:
            return False
        if datetime.now(timezone.utc) > execution.undo_available_until:
            return False
        if not execution.undo_state:
            return False
        return True

    async def get_undo_deadline(self, execution_id: str) -> datetime | None:
        """Get the undo deadline for an execution, or None if not undoable."""
        execution = await self._get_execution(execution_id)
        if not execution:
            return None
        return execution.undo_available_until

    async def undo(self, execution_id: str) -> UndoResult:
        """Undo an execution."""
        if not await self.can_undo(execution_id):
            return UndoResult(False, execution_id, "Cannot undo: expired, already undone, or no undo state")

        execution = await self._get_execution(execution_id)

        try:
            undo_states = json.loads(execution.undo_state)
        except (json.JSONDecodeError, TypeError):
            return UndoResult(False, execution_id, "Invalid undo state")

        # Execute undo for each action in reverse order
        errors = []
        for state in reversed(undo_states):
            try:
                await self._undo_action(state)
            except Exception as e:
                errors.append(str(e))
                logger.error(f"Undo action failed: {e}")

        # Mark as undone regardless of individual action failures
        await self.repo.update_execution(execution_id, status="undone")

        if errors:
            return UndoResult(True, execution_id, f"Undone with {len(errors)} error(s): {'; '.join(errors)}")
        return UndoResult(True, execution_id, "Successfully undone")

    async def cleanup_expired(self) -> int:
        """Clear undo state for executions past their undo window.

        Returns the number of executions cleaned up.
        """
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(WorkflowExecution).where(
                WorkflowExecution.undo_available_until < now,
                WorkflowExecution.undo_state.isnot(None),
                WorkflowExecution.status != "undone",
            )
        )
        expired = list(result.scalars().all())

        if not expired:
            return 0

        for ex in expired:
            await self.repo.update_execution(
                ex.id,
                undo_state=None,
                undo_available_until=None,
            )

        logger.info(f"Cleaned up undo state for {len(expired)} expired executions")
        return len(expired)

    async def _get_execution(self, execution_id: str) -> WorkflowExecution | None:
        result = await self.session.execute(
            select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
        )
        return result.scalar_one_or_none()

    async def _undo_action(self, undo_state: dict) -> None:
        """Undo a single action based on its saved state."""
        action = undo_state.get("action", "")
        # Map undo actions back to handler types
        handler_map = {
            "close_tab": "open_url",
            "close_app": "open_app",
            "undo_type": "type_text",
            "script_ran": "run_script",
            "message_sent": "send_message",
        }
        handler_type = handler_map.get(action)
        if handler_type:
            handler = get_handler(handler_type)
            if handler:
                await handler.undo(undo_state)
                return

        logger.warning(f"No undo handler for action: {action}")
