"""Capture upload API endpoints.

Provides endpoints for uploading and retrieving screenshot captures.
All file storage is delegated to FileStorage, with metadata in PostgreSQL.
"""

import json
from datetime import datetime
from functools import lru_cache
from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jarvis_server.config import get_settings
from jarvis_server.db.models import Capture
from jarvis_server.db.session import get_db
from jarvis_server.storage.filesystem import FileStorage

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/captures", tags=["captures"])


# --- Dependencies ---


@lru_cache
def get_storage() -> FileStorage:
    """Get cached FileStorage instance configured from settings.

    Uses lru_cache for singleton pattern - storage is initialized once
    and reused for all requests.
    """
    settings = get_settings()
    return FileStorage(base_path=settings.storage_path)


# --- Schemas ---


class CaptureMetadata(BaseModel):
    """Metadata submitted with capture upload."""

    timestamp: datetime
    monitor_index: int = 0
    width: int
    height: int
    agent_id: str | None = None


class CaptureResponse(BaseModel):
    """Response returned after successful capture upload."""

    id: str
    status: str
    filepath: str


class CaptureDetail(BaseModel):
    """Detailed capture information for retrieval."""

    id: str
    filepath: str
    timestamp: datetime
    monitor_index: int
    width: int
    height: int
    file_size: int
    ocr_text: str | None
    created_at: datetime


# --- Endpoints ---


@router.post("/", response_model=CaptureResponse)
async def upload_capture(
    file: UploadFile = File(...),
    metadata: str = Form(...),
    db: AsyncSession = Depends(get_db),
    storage: FileStorage = Depends(get_storage),
) -> CaptureResponse:
    """Upload a capture image with metadata.

    Accepts multipart form data with:
    - file: JPEG image file
    - metadata: JSON string containing CaptureMetadata fields

    Returns the capture ID and storage path.
    """
    log = logger.bind(content_type=file.content_type, filename=file.filename)

    # Validate content type
    if file.content_type not in ("image/jpeg", "image/jpg"):
        log.warning("invalid_content_type", content_type=file.content_type)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file.content_type}. Expected image/jpeg.",
        )

    # Parse metadata JSON
    try:
        meta_dict = json.loads(metadata)
        meta = CaptureMetadata(**meta_dict)
    except json.JSONDecodeError as e:
        log.warning("invalid_metadata_json", error=str(e))
        raise HTTPException(status_code=400, detail=f"Invalid metadata JSON: {e}")
    except Exception as e:
        log.warning("invalid_metadata_schema", error=str(e))
        raise HTTPException(status_code=400, detail=f"Invalid metadata: {e}")

    # Generate capture ID
    capture_id = str(uuid4())
    log = log.bind(capture_id=capture_id, timestamp=meta.timestamp.isoformat())

    # Read file content
    file_content = await file.read()
    file_size = len(file_content)

    log.info("storing_capture", file_size=file_size)

    # Store file to filesystem
    try:
        filepath = await storage.store(
            capture_id=capture_id,
            data=file_content,
            timestamp=meta.timestamp,
        )
    except Exception as e:
        log.error("storage_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to store capture file")

    # Create database record
    capture = Capture(
        id=capture_id,
        filepath=str(filepath),
        timestamp=meta.timestamp,
        monitor_index=meta.monitor_index,
        width=meta.width,
        height=meta.height,
        file_size=file_size,
        ocr_text=None,  # Populated later by processing pipeline
    )

    try:
        db.add(capture)
        await db.commit()
        log.info("capture_stored", filepath=str(filepath))
    except Exception as e:
        log.error("database_failed", error=str(e))
        # Try to clean up the stored file
        await storage.delete(filepath)
        raise HTTPException(status_code=500, detail="Failed to save capture metadata")

    return CaptureResponse(
        id=capture_id,
        status="stored",
        filepath=str(filepath),
    )


@router.get("/{capture_id}", response_model=CaptureDetail)
async def get_capture(
    capture_id: str,
    db: AsyncSession = Depends(get_db),
) -> CaptureDetail:
    """Get capture metadata by ID.

    Returns capture details including filepath, dimensions, and OCR text.
    Does not return the actual image file (use filepath to retrieve).
    """
    log = logger.bind(capture_id=capture_id)

    result = await db.execute(select(Capture).where(Capture.id == capture_id))
    capture = result.scalar_one_or_none()

    if capture is None:
        log.info("capture_not_found")
        raise HTTPException(status_code=404, detail="Capture not found")

    log.info("capture_retrieved")

    return CaptureDetail(
        id=capture.id,
        filepath=capture.filepath,
        timestamp=capture.timestamp,
        monitor_index=capture.monitor_index,
        width=capture.width,
        height=capture.height,
        file_size=capture.file_size,
        ocr_text=capture.ocr_text,
        created_at=capture.created_at,
    )
