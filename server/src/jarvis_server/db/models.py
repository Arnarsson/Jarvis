"""SQLAlchemy 2.0 ORM models for Jarvis database schema."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from jarvis_server.db.base import Base


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

    # Processing status: pending, processing, completed, failed
    processing_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )

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

    # Indices for common query patterns
    __table_args__ = (
        Index("ix_captures_timestamp", "timestamp"),
        Index("ix_captures_processing_status", "processing_status"),
    )

    def __repr__(self) -> str:
        return f"<Capture(id={self.id}, timestamp={self.timestamp}, monitor={self.monitor_index})>"


class ConversationRecord(Base):
    """Imported AI conversation metadata."""

    __tablename__ = "conversations"

    # Primary key: UUID as string
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )

    # External ID from source system
    external_id: Mapped[str] = mapped_column(String(100), nullable=False)

    # Source: chatgpt, claude, grok
    source: Mapped[str] = mapped_column(String(20), nullable=False)

    # Conversation title
    title: Mapped[str] = mapped_column(String(500), nullable=False)

    # Full conversation text (for display)
    full_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Message count
    message_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # When conversation was created (from source)
    conversation_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # When imported into Jarvis
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Processing status for embedding
    processing_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )

    __table_args__ = (
        Index("ix_conversations_source", "source"),
        Index("ix_conversations_date", "conversation_date"),
        Index("ix_conversations_external_id", "external_id", "source", unique=True),
    )
