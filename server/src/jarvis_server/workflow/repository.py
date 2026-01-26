"""Pattern repository for workflow automation CRUD operations."""

import json
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.db.models import Pattern, PatternOccurrence, WorkflowExecution


class PatternRepository:
    """Repository for pattern CRUD operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_pattern(
        self,
        name: str,
        pattern_type: str,
        trigger_conditions: dict,
        actions: list,
        description: Optional[str] = None,
    ) -> Pattern:
        """Create a new pattern."""
        pattern = Pattern(
            id=str(uuid4()),
            name=name,
            description=description,
            pattern_type=pattern_type,
            trigger_conditions=json.dumps(trigger_conditions),
            actions=json.dumps(actions),
            trust_tier="observe",
            is_active=True,
            frequency_count=1,
            last_seen=datetime.now(timezone.utc),
        )
        self.session.add(pattern)
        await self.session.commit()
        await self.session.refresh(pattern)
        return pattern

    async def get_pattern(self, pattern_id: str) -> Optional[Pattern]:
        """Get a pattern by ID."""
        result = await self.session.execute(
            select(Pattern).where(Pattern.id == pattern_id)
        )
        return result.scalar_one_or_none()

    async def list_patterns(
        self,
        trust_tier: Optional[str] = None,
        active_only: bool = True,
        pattern_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[Pattern]:
        """List patterns with optional filters."""
        query = select(Pattern)
        
        if active_only:
            query = query.where(Pattern.is_active == True)
        if trust_tier:
            query = query.where(Pattern.trust_tier == trust_tier)
        if pattern_type:
            query = query.where(Pattern.pattern_type == pattern_type)
        
        query = query.order_by(Pattern.frequency_count.desc()).limit(limit)
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_pattern(
        self,
        pattern_id: str,
        **kwargs,
    ) -> Optional[Pattern]:
        """Update a pattern."""
        # Convert dict fields to JSON
        if "trigger_conditions" in kwargs and isinstance(kwargs["trigger_conditions"], dict):
            kwargs["trigger_conditions"] = json.dumps(kwargs["trigger_conditions"])
        if "actions" in kwargs and isinstance(kwargs["actions"], list):
            kwargs["actions"] = json.dumps(kwargs["actions"])
        
        kwargs["updated_at"] = datetime.now(timezone.utc)
        
        await self.session.execute(
            update(Pattern).where(Pattern.id == pattern_id).values(**kwargs)
        )
        await self.session.commit()
        return await self.get_pattern(pattern_id)

    async def increment_frequency(self, pattern_id: str) -> None:
        """Increment frequency count and update last_seen."""
        pattern = await self.get_pattern(pattern_id)
        if pattern:
            await self.session.execute(
                update(Pattern)
                .where(Pattern.id == pattern_id)
                .values(
                    frequency_count=pattern.frequency_count + 1,
                    last_seen=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await self.session.commit()

    async def promote_tier(self, pattern_id: str, new_tier: str) -> Optional[Pattern]:
        """Promote a pattern to a new trust tier."""
        if new_tier not in ["observe", "suggest", "auto"]:
            raise ValueError(f"Invalid trust tier: {new_tier}")
        return await self.update_pattern(pattern_id, trust_tier=new_tier)

    async def suspend_pattern(self, pattern_id: str, reason: str) -> Optional[Pattern]:
        """Suspend a pattern."""
        return await self.update_pattern(
            pattern_id,
            is_active=False,
            suspension_reason=reason,
            trust_tier="observe",
        )

    async def unsuspend_pattern(self, pattern_id: str) -> Optional[Pattern]:
        """Reactivate a suspended pattern."""
        return await self.update_pattern(
            pattern_id,
            is_active=True,
            suspension_reason=None,
        )

    async def record_occurrence(
        self,
        pattern_id: str,
        capture_id: str,
        context: Optional[dict] = None,
        confidence: float = 0.5,
    ) -> PatternOccurrence:
        """Record a pattern occurrence."""
        occurrence = PatternOccurrence(
            id=str(uuid4()),
            pattern_id=pattern_id,
            capture_id=capture_id,
            context=json.dumps(context) if context else None,
            confidence_score=confidence,
        )
        self.session.add(occurrence)
        await self.session.commit()
        
        # Also increment pattern frequency
        await self.increment_frequency(pattern_id)
        
        return occurrence

    async def get_pattern_stats(self, pattern_id: str) -> dict:
        """Get statistics for a pattern."""
        pattern = await self.get_pattern(pattern_id)
        if not pattern:
            return {}
        
        accuracy = 0.0
        if pattern.total_executions > 0:
            accuracy = pattern.correct_executions / pattern.total_executions
        
        return {
            "frequency_count": pattern.frequency_count,
            "last_seen": pattern.last_seen,
            "total_executions": pattern.total_executions,
            "correct_executions": pattern.correct_executions,
            "accuracy": accuracy,
            "trust_tier": pattern.trust_tier,
            "is_active": pattern.is_active,
        }

    async def record_execution(
        self,
        pattern_id: str,
        trigger_capture_id: Optional[str] = None,
        user_approved: bool = False,
    ) -> WorkflowExecution:
        """Record a workflow execution."""
        execution = WorkflowExecution(
            id=str(uuid4()),
            pattern_id=pattern_id,
            trigger_capture_id=trigger_capture_id,
            status="pending",
            user_approved=user_approved,
        )
        self.session.add(execution)
        await self.session.commit()
        await self.session.refresh(execution)
        return execution

    async def update_execution(
        self,
        execution_id: str,
        **kwargs,
    ) -> Optional[WorkflowExecution]:
        """Update an execution record."""
        if "result" in kwargs and isinstance(kwargs["result"], (dict, list)):
            kwargs["result"] = json.dumps(kwargs["result"])
        if "undo_state" in kwargs and isinstance(kwargs["undo_state"], (dict, list)):
            kwargs["undo_state"] = json.dumps(kwargs["undo_state"])
        
        await self.session.execute(
            update(WorkflowExecution)
            .where(WorkflowExecution.id == execution_id)
            .values(**kwargs)
        )
        await self.session.commit()
        
        result = await self.session.execute(
            select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
        )
        return result.scalar_one_or_none()

    async def record_feedback(
        self,
        execution_id: str,
        was_correct: bool,
    ) -> None:
        """Record user feedback on an execution."""
        result = await self.session.execute(
            select(WorkflowExecution).where(WorkflowExecution.id == execution_id)
        )
        execution = result.scalar_one_or_none()
        if not execution:
            return
        
        # Update execution
        await self.update_execution(execution_id, was_correct=was_correct)
        
        # Update pattern stats
        pattern = await self.get_pattern(execution.pattern_id)
        if pattern:
            new_total = pattern.total_executions + 1
            new_correct = pattern.correct_executions + (1 if was_correct else 0)
            await self.update_pattern(
                pattern.id,
                total_executions=new_total,
                correct_executions=new_correct,
            )
