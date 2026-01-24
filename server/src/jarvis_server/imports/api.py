"""Import API endpoints for AI chat exports."""
import logging
import tempfile
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..db.session import get_db
from ..db.models import ConversationRecord
from ..vector.qdrant import get_qdrant
from ..processing.embeddings import get_embedding_processor
from .chatgpt import parse_chatgpt_export
from .claude import parse_claude_export
from .grok import parse_grok_export

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/import", tags=["import"])

PARSERS = {
    "chatgpt": parse_chatgpt_export,
    "claude": parse_claude_export,
    "grok": parse_grok_export,
}


class ImportResponse(BaseModel):
    """Response from import endpoint."""
    imported: int
    skipped: int
    errors: int
    source: str


@router.post("/", response_model=ImportResponse)
async def import_conversations(
    file: UploadFile = File(...),
    source: Literal["chatgpt", "claude", "grok"] = Form(...),
    db: AsyncSession = Depends(get_db),
) -> ImportResponse:
    """Import AI chat export file.

    Supported formats:
    - chatgpt: conversations.json from ChatGPT data export
    - claude: ZIP or JSON from Claude export
    - grok: JSON from Grok export

    Conversations are stored in database and queued for embedding.
    Duplicate conversations (same external_id + source) are skipped.
    """
    if source not in PARSERS:
        raise HTTPException(status_code=400, detail=f"Unknown source: {source}")

    parser = PARSERS[source]

    # Save uploaded file to temp location
    suffix = ".zip" if source == "claude" and file.filename and file.filename.endswith(".zip") else ".json"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    imported = 0
    skipped = 0
    errors = 0

    try:
        qdrant = get_qdrant()
        embedder = get_embedding_processor()

        for conversation in parser(tmp_path):
            try:
                # Check if already exists
                existing = await db.execute(
                    select(ConversationRecord.id)
                    .where(ConversationRecord.external_id == conversation.id)
                    .where(ConversationRecord.source == source)
                )
                if existing.scalar_one_or_none():
                    skipped += 1
                    continue

                # Create database record
                record = ConversationRecord(
                    id=str(uuid4()),
                    external_id=conversation.id,
                    source=source,
                    title=conversation.title,
                    full_text=conversation.full_text,
                    message_count=conversation.message_count,
                    conversation_date=conversation.created_at,
                    processing_status="processing",
                )
                db.add(record)
                await db.flush()

                # Generate embedding
                if conversation.full_text.strip():
                    embedding = embedder.embed(conversation.full_text)

                    # Store in Qdrant
                    qdrant.upsert_capture(
                        capture_id=record.id,
                        dense_vector=embedding.dense.tolist(),
                        sparse_indices=embedding.sparse_indices,
                        sparse_values=embedding.sparse_values,
                        payload={
                            "timestamp": conversation.created_at.isoformat() if conversation.created_at else None,
                            "text_preview": conversation.full_text[:500],
                            "source": source,
                            "title": conversation.title,
                        },
                    )

                record.processing_status = "completed"
                imported += 1

            except Exception as e:
                logger.warning(f"Failed to import conversation {conversation.id}: {e}")
                errors += 1
                await db.rollback()

        await db.commit()

    finally:
        # Cleanup temp file
        tmp_path.unlink(missing_ok=True)

    logger.info(f"Import complete: {imported} imported, {skipped} skipped, {errors} errors")

    return ImportResponse(
        imported=imported,
        skipped=skipped,
        errors=errors,
        source=source,
    )


@router.get("/sources")
async def list_import_sources() -> dict:
    """List available import sources."""
    return {
        "sources": [
            {
                "id": "chatgpt",
                "name": "ChatGPT",
                "format": "conversations.json",
                "instructions": "ChatGPT Settings -> Data Controls -> Export data",
            },
            {
                "id": "claude",
                "name": "Claude",
                "format": "ZIP or JSON",
                "instructions": "Claude.ai -> Settings -> Export conversations",
            },
            {
                "id": "grok",
                "name": "Grok",
                "format": "JSON",
                "instructions": "accounts.x.ai -> Export data",
            },
        ]
    }
