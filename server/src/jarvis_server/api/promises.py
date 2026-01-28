"""Promise Tracker API - detect and track commitments from conversations.

Tracks promises and commitments detected in conversations with status tracking.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.db.session import get_db
from jarvis_server.db.models import Promise

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v2/promises", tags=["promises"])


# Request/Response Models
class PromiseResponse(BaseModel):
    """Promise response."""
    id: str
    text: str
    source_conversation_id: str | None
    detected_at: str
    due_by: str | None
    status: str
    fulfilled_at: str | None


class PromisesListResponse(BaseModel):
    """List of promises."""
    promises: list[PromiseResponse]
    total: int


@router.get("", response_model=PromisesListResponse)
async def list_promises(
    status: str | None = Query(None, description="Filter by status: pending|fulfilled|broken"),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
) -> PromisesListResponse:
    """List promises with optional status filter.
    
    Returns promises ordered by detection time (newest first).
    """
    try:
        # Build query
        query = select(Promise).order_by(Promise.detected_at.desc()).limit(limit)
        
        # Apply status filter if provided
        if status:
            if status not in ("pending", "fulfilled", "broken"):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid status. Must be: pending, fulfilled, or broken"
                )
            query = query.where(Promise.status == status)
        
        # Execute query
        result = await db.execute(query)
        promises = result.scalars().all()
        
        # Format response
        promise_list = [
            PromiseResponse(
                id=p.id,
                text=p.text,
                source_conversation_id=p.source_conversation_id,
                detected_at=p.detected_at.isoformat(),
                due_by=p.due_by.isoformat() if p.due_by else None,
                status=p.status,
                fulfilled_at=p.fulfilled_at.isoformat() if p.fulfilled_at else None,
            )
            for p in promises
        ]
        
        logger.info("promises_listed", count=len(promise_list), status_filter=status)
        
        return PromisesListResponse(
            promises=promise_list,
            total=len(promise_list)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("promises_list_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list promises")


@router.patch("/{promise_id}/status")
async def update_promise_status(
    promise_id: str,
    status: str = Query(..., description="New status: pending|fulfilled|broken"),
    db: AsyncSession = Depends(get_db),
) -> PromiseResponse:
    """Update promise status."""
    try:
        if status not in ("pending", "fulfilled", "broken"):
            raise HTTPException(
                status_code=400,
                detail="Invalid status. Must be: pending, fulfilled, or broken"
            )
        
        # Fetch promise
        result = await db.execute(
            select(Promise).where(Promise.id == promise_id)
        )
        promise = result.scalar_one_or_none()
        
        if not promise:
            raise HTTPException(status_code=404, detail="Promise not found")
        
        # Update status
        promise.status = status
        
        # Set fulfilled_at if marking as fulfilled
        if status == "fulfilled" and not promise.fulfilled_at:
            from datetime import datetime
            promise.fulfilled_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(promise)
        
        logger.info("promise_status_updated", id=promise_id, new_status=status)
        
        return PromiseResponse(
            id=promise.id,
            text=promise.text,
            source_conversation_id=promise.source_conversation_id,
            detected_at=promise.detected_at.isoformat(),
            due_by=promise.due_by.isoformat() if promise.due_by else None,
            status=promise.status,
            fulfilled_at=promise.fulfilled_at.isoformat() if promise.fulfilled_at else None,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("promise_status_update_failed", error=str(e), id=promise_id)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update promise status")
