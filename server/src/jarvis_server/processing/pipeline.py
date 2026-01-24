"""Processing pipeline orchestration."""

import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import Capture
from ..vector.qdrant import QdrantWrapper
from .embeddings import EmbeddingProcessor
from .ocr import OCRProcessor

logger = logging.getLogger(__name__)


async def process_single_capture(
    db: AsyncSession,
    capture_id: str,
    ocr: OCRProcessor,
    embedder: EmbeddingProcessor,
    qdrant: QdrantWrapper,
) -> dict:
    """Process a single capture: OCR -> embed -> store in Qdrant.

    Returns dict with status and details.
    """
    # 1. Load capture from database
    result = await db.execute(select(Capture).where(Capture.id == capture_id))
    capture = result.scalar_one_or_none()

    if not capture:
        return {"status": "not_found", "id": capture_id}

    # 2. Mark as processing
    await db.execute(
        update(Capture).where(Capture.id == capture_id).values(processing_status="processing")
    )
    await db.commit()

    try:
        # 3. Run OCR
        text = ocr.extract_text(capture.filepath)

        # 4. Update database with OCR text
        await db.execute(update(Capture).where(Capture.id == capture_id).values(ocr_text=text))
        await db.commit()

        # 5. Generate embeddings (skip if no text)
        if text.strip():
            embedding = embedder.embed(text)

            # 6. Store in Qdrant
            qdrant.upsert_capture(
                capture_id=capture_id,
                dense_vector=embedding.dense.tolist(),
                sparse_indices=embedding.sparse_indices,
                sparse_values=embedding.sparse_values,
                payload={
                    "timestamp": capture.timestamp.isoformat(),
                    "filepath": capture.filepath,
                    "text_preview": text[:500],
                    "source": "screen",
                },
            )

        # 7. Mark completed
        await db.execute(
            update(Capture).where(Capture.id == capture_id).values(processing_status="completed")
        )
        await db.commit()

        return {
            "status": "processed",
            "id": capture_id,
            "text_length": len(text),
            "has_embedding": bool(text.strip()),
        }

    except Exception as e:
        logger.error(f"Failed to process capture {capture_id}: {e}")
        await db.execute(
            update(Capture).where(Capture.id == capture_id).values(processing_status="failed")
        )
        await db.commit()
        return {"status": "failed", "id": capture_id, "error": str(e)}


async def get_pending_captures(db: AsyncSession, limit: int = 100) -> list[str]:
    """Get capture IDs pending processing."""
    result = await db.execute(
        select(Capture.id)
        .where(Capture.processing_status == "pending")
        .order_by(Capture.timestamp.asc())
        .limit(limit)
    )
    return [row[0] for row in result.fetchall()]
