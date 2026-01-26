"""ARQ worker configuration and settings."""

import logging

from arq import cron
from arq.connections import RedisSettings

from ..config import get_settings
from ..vector.qdrant import get_qdrant, setup_captures_collection
from .embeddings import get_embedding_processor
from .ocr import get_ocr_processor
from ..meetings.tasks import summarize_meeting_task
from ..transcription.tasks import transcribe_meeting_task
from ..workflow.queue import execute_workflow_task, cleanup_expired_undos
from .tasks import (
    process_backlog,
    process_capture,
    process_email_embeddings,
    sync_calendar_task,
)

logger = logging.getLogger(__name__)


def _get_redis_settings() -> RedisSettings:
    """Get Redis connection settings from config."""
    settings = get_settings()
    return RedisSettings(
        host=settings.redis_host,
        port=settings.redis_port,
    )


class WorkerSettings:
    """ARQ worker settings for background processing."""

    # Register task functions
    functions = [
        process_capture,
        process_backlog,
        sync_calendar_task,
        process_email_embeddings,
        transcribe_meeting_task,
        summarize_meeting_task,
        execute_workflow_task,
    ]

    # Cron jobs
    cron_jobs = [
        cron(process_backlog, hour={0, 6, 12, 18}, minute=0),  # Every 6 hours
        cron(cleanup_expired_undos, hour={3}, minute=0),  # Daily at 3am
    ]

    # Worker limits
    max_jobs = 5  # Limit concurrent OCR jobs (memory intensive)
    job_timeout = 300  # 5 minutes per capture

    # Redis connection settings (loaded at worker startup)
    redis_settings = _get_redis_settings()

    @staticmethod
    async def on_startup(ctx: dict) -> None:
        """Initialize shared resources for worker."""
        logger.info("ARQ worker starting up...")

        # Initialize processing components (lazy-loaded on first use)
        ctx["ocr"] = get_ocr_processor()
        ctx["embedder"] = get_embedding_processor()
        ctx["qdrant"] = get_qdrant()

        # Ensure Qdrant collection exists
        setup_captures_collection(ctx["qdrant"])

        logger.info("ARQ worker ready")

    @staticmethod
    async def on_shutdown(ctx: dict) -> None:
        """Cleanup on worker shutdown."""
        logger.info("ARQ worker shutting down...")


# Entry point for arq CLI: arq jarvis_server.processing.worker.WorkerSettings
