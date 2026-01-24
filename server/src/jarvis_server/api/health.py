"""Health check API endpoints.

Provides endpoints for monitoring server health and readiness.
"""

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server import __version__
from jarvis_server.api.captures import get_storage
from jarvis_server.db.session import get_db
from jarvis_server.storage.filesystem import FileStorage

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


# --- Schemas ---


class HealthResponse(BaseModel):
    """Health check response with component status."""

    status: str = "healthy"
    version: str
    database: str = "unknown"
    storage: str = "unknown"


# --- Endpoints ---


@router.get("/", response_model=HealthResponse)
async def health_check(
    db: AsyncSession = Depends(get_db),
    storage: FileStorage = Depends(get_storage),
) -> HealthResponse:
    """Check server health and component status.

    Always returns 200 with component status in body.
    Monitoring systems should check the body for unhealthy components.
    """
    database_status = "unknown"
    storage_status = "unknown"
    overall_status = "healthy"

    # Check database connectivity
    try:
        await db.execute(text("SELECT 1"))
        database_status = "healthy"
    except Exception as e:
        logger.warning("database_health_check_failed", error=str(e))
        database_status = "unhealthy"
        overall_status = "degraded"

    # Check storage path exists and is writable
    try:
        if storage.base_path.exists() and storage.base_path.is_dir():
            # Try to check write permission
            test_file = storage.base_path / ".health_check"
            try:
                test_file.touch()
                test_file.unlink()
                storage_status = "healthy"
            except PermissionError:
                storage_status = "read-only"
                overall_status = "degraded"
        else:
            storage_status = "not-configured"
            overall_status = "degraded"
    except Exception as e:
        logger.warning("storage_health_check_failed", error=str(e))
        storage_status = "unhealthy"
        overall_status = "degraded"

    return HealthResponse(
        status=overall_status,
        version=__version__,
        database=database_status,
        storage=storage_status,
    )


@router.get("/ready")
async def readiness_check(
    db: AsyncSession = Depends(get_db),
    storage: FileStorage = Depends(get_storage),
) -> dict:
    """Check if server is ready to accept traffic.

    Returns 200 only if all components are healthy.
    Returns 503 if any component is unhealthy.

    Used by load balancers and orchestrators for routing decisions.
    """
    from fastapi import HTTPException

    # Check database
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        logger.warning("readiness_database_failed", error=str(e))
        raise HTTPException(status_code=503, detail="Database not ready")

    # Check storage
    if not storage.base_path.exists():
        logger.warning("readiness_storage_failed", reason="path_not_exists")
        raise HTTPException(status_code=503, detail="Storage path not configured")

    try:
        test_file = storage.base_path / ".ready_check"
        test_file.touch()
        test_file.unlink()
    except Exception as e:
        logger.warning("readiness_storage_failed", error=str(e))
        raise HTTPException(status_code=503, detail="Storage not writable")

    return {"ready": True}
