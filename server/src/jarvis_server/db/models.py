"""SQLAlchemy 2.0 ORM models for Jarvis database schema."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text, func
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


# =============================================================================
# Workflow Automation Models (Phase 6)
# =============================================================================


class Pattern(Base):
    """Detected workflow pattern from screen captures.
    
    Patterns are repeated action sequences that can be automated.
    Trust tiers: observe -> suggest -> auto
    """

    __tablename__ = "patterns"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )

    # Human-readable name and description
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Pattern type: REPETITIVE_ACTION, TIME_BASED, TRIGGER_RESPONSE, WORKFLOW_SEQUENCE
    pattern_type: Mapped[str] = mapped_column(String(30), nullable=False)

    # JSON: What triggers this pattern
    trigger_conditions: Mapped[str] = mapped_column(Text, nullable=False)  # JSON

    # JSON: What actions to perform
    actions: Mapped[str] = mapped_column(Text, nullable=False)  # JSON

    # How often this pattern has been detected
    frequency_count: Mapped[int] = mapped_column(Integer, default=1)

    # Last time this pattern was detected
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Trust tier: observe (watching), suggest (propose to user), auto (execute automatically)
    trust_tier: Mapped[str] = mapped_column(String(20), default="observe", nullable=False)

    # Is this pattern currently active (vs suspended/rejected)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Why suspended (if applicable)
    suspension_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Accuracy tracking
    total_executions: Mapped[int] = mapped_column(Integer, default=0)
    correct_executions: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_patterns_trust_tier", "trust_tier"),
        Index("ix_patterns_is_active", "is_active"),
        Index("ix_patterns_pattern_type", "pattern_type"),
    )


class PatternOccurrence(Base):
    """Record of when a pattern was detected in a capture."""

    __tablename__ = "pattern_occurrences"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )

    # Foreign key to pattern
    pattern_id: Mapped[str] = mapped_column(String(36), nullable=False)

    # Foreign key to capture that triggered detection
    capture_id: Mapped[str] = mapped_column(String(36), nullable=False)

    # JSON: Context information about the detection
    context: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON

    # How confident we are this is a valid match (0.0 - 1.0)
    confidence_score: Mapped[float] = mapped_column(default=0.5, nullable=False)

    # When detected
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_pattern_occurrences_pattern_id", "pattern_id"),
        Index("ix_pattern_occurrences_capture_id", "capture_id"),
        Index("ix_pattern_occurrences_detected_at", "detected_at"),
    )


class WorkflowExecution(Base):
    """Record of automated workflow execution."""

    __tablename__ = "workflow_executions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )

    # Foreign key to pattern that was executed
    pattern_id: Mapped[str] = mapped_column(String(36), nullable=False)

    # Foreign key to capture that triggered execution
    trigger_capture_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Execution status: pending, running, completed, failed, cancelled, undone
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # JSON: Result of execution
    result: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON

    # Error message if failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Was this manually approved (vs auto-executed)
    user_approved: Mapped[bool] = mapped_column(default=False, nullable=False)

    # Undo window deadline
    undo_available_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # JSON: State needed for undo
    undo_state: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON

    # User feedback: true=correct, false=incorrect, null=no feedback
    was_correct: Mapped[bool | None] = mapped_column(nullable=True)

    # When created
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_workflow_executions_pattern_id", "pattern_id"),
        Index("ix_workflow_executions_status", "status"),
        Index("ix_workflow_executions_created_at", "created_at"),
    )
