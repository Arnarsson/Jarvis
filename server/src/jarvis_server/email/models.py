"""SQLAlchemy models for email messages."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from jarvis_server.db.base import Base


class EmailSyncState(Base):
    """Stores history ID for incremental Gmail sync.

    Gmail uses history IDs to track changes since the last sync,
    enabling efficient incremental syncs instead of full refreshes.
    """

    __tablename__ = "email_sync_states"

    id: Mapped[str] = mapped_column(
        String(50), primary_key=True
    )  # e.g., "gmail_primary"
    history_id: Mapped[str] = mapped_column(String(50), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<EmailSyncState(id={self.id}, history_id={self.history_id})>"


class EmailMessage(Base):
    """Gmail message synced to Jarvis.

    Stores email messages from Gmail for context building,
    search, and AI-powered summarization.
    """

    __tablename__ = "email_messages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    gmail_message_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    thread_id: Mapped[str] = mapped_column(String(100), nullable=False)

    # Message details
    subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    from_address: Mapped[str | None] = mapped_column(String(200), nullable=True)
    from_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    to_addresses: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array
    cc_addresses: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array

    # Content
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)  # Gmail's snippet
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)  # Plain text body

    # Timing
    date_sent: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    date_received: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Labels/flags
    labels_json: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # JSON array of label IDs
    is_unread: Mapped[bool] = mapped_column(default=False)
    is_important: Mapped[bool] = mapped_column(default=False)

    # Classification
    category: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )  # priority, newsletter, notification, low_priority

    # Processing status
    processing_status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending, processed, failed
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Sync metadata
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_email_messages_date_sent", "date_sent"),
        Index("ix_email_messages_gmail_id", "gmail_message_id"),
        Index("ix_email_messages_from", "from_address"),
        Index("ix_email_messages_thread", "thread_id"),
        Index("ix_email_messages_category", "category"),
    )

    def __repr__(self) -> str:
        return f"<EmailMessage(id={self.id}, subject={self.subject}, from={self.from_address})>"
