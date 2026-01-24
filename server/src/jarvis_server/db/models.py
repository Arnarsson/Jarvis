"""SQLAlchemy 2.0 ORM models for Jarvis database schema."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class Capture(Base):
    """Screenshot capture metadata.

    Stores metadata about captured screenshots. The actual image files
    are stored on the filesystem in a date-partitioned structure, with
    the filepath stored here for retrieval.
    """

    __tablename__ = "captures"

    # Primary key: UUID as string (36 chars with hyphens)
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )

    # File storage location
    filepath: Mapped[str] = mapped_column(String(500), nullable=False)

    # Capture timestamp (when screenshot was taken)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # Monitor information
    monitor_index: Mapped[int] = mapped_column(Integer, default=0)

    # Image dimensions
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)

    # File size in bytes
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)

    # OCR extracted text (populated later by processing pipeline)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metadata timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Index for time-range queries (most common access pattern)
    __table_args__ = (
        Index("ix_captures_timestamp", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<Capture(id={self.id}, timestamp={self.timestamp}, monitor={self.monitor_index})>"
