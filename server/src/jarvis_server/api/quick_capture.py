"""Quick Capture API - save thoughts, ideas, and notes instantly.

Provides a simple text capture endpoint with optional tagging and
automatic memory linking.
"""

import logging
from datetime import datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.db.session import get_db
from jarvis_server.db.models import QuickCapture

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v2/captures", tags=["quick_capture"])


# Request/Response Models
class QuickCaptureCreate(BaseModel):
    """Request to create a quick capture."""
    text: str
    tags: list[str] = []


class QuickCaptureResponse(BaseModel):
    """Quick capture response."""
    id: str
    text: str
    tags: list[str]
    created_at: str
    source: str


class QuickCapturesListResponse(BaseModel):
    """List of quick captures."""
    captures: list[QuickCaptureResponse]
    total: int


@router.post("/quick", response_model=QuickCaptureResponse)
async def create_quick_capture(
    capture: QuickCaptureCreate,
    db: AsyncSession = Depends(get_db),
) -> QuickCaptureResponse:
    """Create a quick capture.
    
    Saves a text note with optional tags for later retrieval.
    """
    try:
        # Create new capture
        new_capture = QuickCapture(
            text=capture.text,
            tags=capture.tags,
            source="manual",  # Could be extended: voice, telegram, etc.
        )
        
        db.add(new_capture)
        await db.commit()
        await db.refresh(new_capture)
        
        logger.info("quick_capture_created", id=new_capture.id, tags=capture.tags)
        
        return QuickCaptureResponse(
            id=new_capture.id,
            text=new_capture.text,
            tags=new_capture.tags,
            created_at=new_capture.created_at.isoformat(),
            source=new_capture.source,
        )
        
    except Exception as e:
        logger.error("quick_capture_failed", error=str(e))
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to create capture")


@router.get("/quick", response_model=QuickCapturesListResponse)
async def list_quick_captures(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> QuickCapturesListResponse:
    """List recent quick captures.
    
    Returns captures ordered by creation time (newest first).
    """
    try:
        # Fetch recent captures
        result = await db.execute(
            select(QuickCapture)
            .order_by(QuickCapture.created_at.desc())
            .limit(min(limit, 200))
        )
        captures = result.scalars().all()
        
        capture_list = [
            QuickCaptureResponse(
                id=c.id,
                text=c.text,
                tags=c.tags,
                created_at=c.created_at.isoformat(),
                source=c.source,
            )
            for c in captures
        ]
        
        logger.info("quick_captures_listed", count=len(capture_list))
        
        return QuickCapturesListResponse(
            captures=capture_list,
            total=len(capture_list)
        )
        
    except Exception as e:
        logger.error("quick_captures_list_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to list captures")


@router.delete("/quick/{capture_id}")
async def delete_quick_capture(
    capture_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a quick capture."""
    try:
        result = await db.execute(
            select(QuickCapture).where(QuickCapture.id == capture_id)
        )
        capture = result.scalar_one_or_none()
        
        if not capture:
            raise HTTPException(status_code=404, detail="Capture not found")
        
        await db.delete(capture)
        await db.commit()
        
        logger.info("quick_capture_deleted", id=capture_id)
        
        return {"status": "deleted", "id": capture_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("quick_capture_delete_failed", error=str(e), id=capture_id)
        await db.rollback()
        raise HTTPException(status_code=500, detail="Failed to delete capture")
