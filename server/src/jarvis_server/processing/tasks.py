"""ARQ task definitions for background processing."""

import logging

from ..db.session import AsyncSessionLocal
from ..vector.qdrant import get_qdrant
from .embeddings import get_embedding_processor
from .ocr import get_ocr_processor
from .pipeline import get_pending_captures, process_single_capture

logger = logging.getLogger(__name__)


async def process_capture(ctx: dict, capture_id: str) -> dict:
    """ARQ task: Process a single capture."""
    async with AsyncSessionLocal() as db:
        result = await process_single_capture(
            db=db,
            capture_id=capture_id,
            ocr=ctx["ocr"],
            embedder=ctx["embedder"],
            qdrant=ctx["qdrant"],
        )
    logger.info(f"Processed capture {capture_id}: {result['status']}")
    return result


async def process_backlog(ctx: dict) -> dict:
    """ARQ task: Queue all pending captures for processing."""
    async with AsyncSessionLocal() as db:
        pending = await get_pending_captures(db, limit=100)

    redis = ctx["redis"]
    for capture_id in pending:
        await redis.enqueue_job("process_capture", capture_id)

    logger.info(f"Queued {len(pending)} captures for processing")
    return {"queued": len(pending)}
