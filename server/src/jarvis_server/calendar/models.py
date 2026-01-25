"""SQLAlchemy models for calendar events and meetings."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from jarvis_server.db.base import Base


class SyncState(Base):
    """Stores sync tokens for incremental calendar sync.

    Used to track the last sync state with Google Calendar API,
    enabling efficient incremental syncs instead of full refreshes.
    """

    __tablename__ = "sync_states"

    id: Mapped[str] = mapped_column(
        String(50), primary_key=True
    )  # e.g., "calendar_primary"
    token: Mapped[str] = mapped_column(String(500), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<SyncState(id={self.id}, updated_at={self.updated_at})>"


class CalendarEvent(Base):
    """Google Calendar event synced to Jarvis.

    Stores calendar events from Google Calendar for meeting intelligence,
    context building, and pre-meeting briefs.
    """

    __tablename__ = "calendar_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    google_event_id: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    calendar_id: Mapped[str] = mapped_column(String(200), default="primary")

    # Event details
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Timing
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    all_day: Mapped[bool] = mapped_column(default=False)

    # Attendees stored as JSON string
    attendees_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Meeting link (Google Meet, Zoom, etc.)
    meeting_link: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Status: confirmed, tentative, cancelled
    status: Mapped[str] = mapped_column(String(20), default="confirmed")

    # Sync metadata
    etag: Mapped[str | None] = mapped_column(String(100), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_calendar_events_start", "start_time"),
        Index("ix_calendar_events_google_id", "google_event_id"),
    )

    def __repr__(self) -> str:
        return f"<CalendarEvent(id={self.id}, summary={self.summary}, start={self.start_time})>"


class Meeting(Base):
    """Meeting instance with optional recording/transcription.

    Tracks detected meetings (from calendar or window detection),
    their recordings, transcriptions, and AI-generated summaries.
    """

    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    calendar_event_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )  # FK to CalendarEvent

    # Detection info
    platform: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # zoom, google_meet, teams
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Recording (if consent given)
    audio_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    consent_given: Mapped[bool] = mapped_column(default=False)

    # Transcription
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_status: Mapped[str] = mapped_column(
        String(20), default="none"
    )  # none, pending, completed, failed

    # Summary and action items (JSON)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_items_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Pre-meeting brief
    brief: Mapped[str | None] = mapped_column(Text, nullable=True)
    brief_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_meetings_detected_at", "detected_at"),
        Index("ix_meetings_calendar_event", "calendar_event_id"),
    )

    def __repr__(self) -> str:
        return f"<Meeting(id={self.id}, platform={self.platform}, detected={self.detected_at})>"
