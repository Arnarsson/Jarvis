"""Conversations API - full conversation view.

Provides endpoint to fetch full conversation text for memory items.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.db.session import get_db

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v2/conversations", tags=["conversations"])


# Response Models
class ConversationResponse(BaseModel):
    """Full conversation data."""
    id: str
    external_id: str
    source: str
    title: str
    full_text: str
    message_count: int
    conversation_date: str | None
    imported_at: str | None


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    """Get full conversation by ID.
    
    Returns complete conversation text with metadata.
    Used for displaying full context when clicking memory items.
    """
    try:
        # Query conversation from database
        result = await db.execute(
            text(
                "SELECT id, external_id, source, title, full_text, message_count, "
                "conversation_date, imported_at "
                "FROM conversations WHERE id = :id"
            ),
            {"id": conversation_id}
        )
        row = result.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        logger.info("conversation_retrieved", id=conversation_id, source=row[2])
        
        return ConversationResponse(
            id=row[0],
            external_id=row[1],
            source=row[2],
            title=row[3],
            full_text=row[4],
            message_count=row[5],
            conversation_date=row[6].isoformat() if row[6] else None,
            imported_at=row[7].isoformat() if row[7] else None,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("conversation_retrieval_failed", error=str(e), id=conversation_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to retrieve conversation")
