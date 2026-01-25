"""Email embedding generation and storage in Qdrant.

Generates dense and sparse embeddings for email messages and stores them
in the Qdrant vector database for hybrid search alongside other memory sources.
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..processing.embeddings import get_embedding_processor
from ..vector.qdrant import get_qdrant
from .models import EmailMessage

logger = logging.getLogger(__name__)


async def embed_email(message: EmailMessage) -> str:
    """Generate embedding for email and store in Qdrant.

    Creates embedding from: subject + from + body snippet
    Stores with source="email" and metadata for filtering.

    Args:
        message: EmailMessage object to embed

    Returns:
        Point ID of the stored embedding
    """
    # Build text for embedding
    text_parts = []
    if message.subject:
        text_parts.append(f"Email: {message.subject}")
    if message.from_name or message.from_address:
        from_str = message.from_name or message.from_address
        text_parts.append(f"From: {from_str}")
    if message.body_text:
        # Use first ~1000 chars of body for embedding
        text_parts.append(message.body_text[:1000])
    elif message.snippet:
        # Fall back to Gmail snippet if no body
        text_parts.append(message.snippet)

    text = "\n".join(text_parts)

    if not text.strip():
        logger.warning("email_empty_content", message_id=message.id)
        return ""

    # Generate embeddings
    processor = get_embedding_processor()
    embedding = processor.embed(text)

    # Generate point ID
    point_id = str(uuid4())

    # Build text preview for search results
    text_preview = f"Email: {message.subject or '(no subject)'}"
    if message.from_name:
        text_preview += f"\nFrom: {message.from_name}"
    elif message.from_address:
        text_preview += f"\nFrom: {message.from_address}"

    # Ensure timestamp is in ISO format
    timestamp = message.date_sent
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    # Store in Qdrant with email-specific metadata
    qdrant = get_qdrant()
    qdrant.upsert_capture(
        capture_id=point_id,
        dense_vector=embedding.dense.tolist(),
        sparse_indices=embedding.sparse_indices,
        sparse_values=embedding.sparse_values,
        payload={
            "source": "email",
            "message_id": message.id,
            "gmail_id": message.gmail_message_id,
            "subject": message.subject or "",
            "from_address": message.from_address or "",
            "from_name": message.from_name or "",
            "timestamp": timestamp.isoformat(),
            "thread_id": message.thread_id,
            "text_preview": text_preview,
        },
    )

    logger.info("email_embedded", message_id=message.id, point_id=point_id)
    return point_id


async def process_pending_emails(db: AsyncSession, batch_size: int = 10) -> int:
    """Process emails with status=pending.

    Generates embeddings for pending emails and stores them in Qdrant.

    Args:
        db: Async database session
        batch_size: Maximum emails to process per batch

    Returns:
        Count of successfully processed emails
    """
    # Query pending emails
    result = await db.execute(
        select(EmailMessage)
        .where(EmailMessage.processing_status == "pending")
        .limit(batch_size)
    )
    messages = result.scalars().all()

    if not messages:
        logger.debug("no_pending_emails")
        return 0

    processed = 0
    for message in messages:
        try:
            point_id = await embed_email(message)
            if point_id:
                message.processing_status = "processed"
                message.processed_at = datetime.now(timezone.utc)
                processed += 1
            else:
                # Empty content, mark as processed but note it
                message.processing_status = "processed"
                message.processed_at = datetime.now(timezone.utc)
                logger.info("email_skipped_empty", message_id=message.id)
        except Exception:
            logger.exception("email_embedding_failed", message_id=message.id)
            message.processing_status = "failed"

    await db.commit()
    logger.info("email_batch_processed", total=len(messages), success=processed)
    return processed
