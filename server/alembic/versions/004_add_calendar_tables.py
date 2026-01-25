"""Add calendar and meeting tables for Phase 4.

Revision ID: 004
Revises: 003
Create Date: 2026-01-25
"""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Sync state table for incremental sync tokens
    op.create_table(
        "sync_states",
        sa.Column("id", sa.String(50), primary_key=True),
        sa.Column("token", sa.String(500), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Calendar events table
    op.create_table(
        "calendar_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("google_event_id", sa.String(255), nullable=False, unique=True),
        sa.Column("calendar_id", sa.String(200), server_default="primary"),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("location", sa.String(500), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("all_day", sa.Boolean, server_default="false"),
        sa.Column("attendees_json", sa.Text, nullable=True),
        sa.Column("meeting_link", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), server_default="confirmed"),
        sa.Column("etag", sa.String(100), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_calendar_events_start", "calendar_events", ["start_time"])
    op.create_index("ix_calendar_events_google_id", "calendar_events", ["google_event_id"])

    # Meetings table
    op.create_table(
        "meetings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("calendar_event_id", sa.String(36), nullable=True),
        sa.Column("platform", sa.String(50), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("audio_path", sa.String(500), nullable=True),
        sa.Column("consent_given", sa.Boolean, server_default="false"),
        sa.Column("transcript", sa.Text, nullable=True),
        sa.Column("transcript_status", sa.String(20), server_default="none"),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("action_items_json", sa.Text, nullable=True),
        sa.Column("brief", sa.Text, nullable=True),
        sa.Column("brief_generated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_meetings_detected_at", "meetings", ["detected_at"])
    op.create_index("ix_meetings_calendar_event", "meetings", ["calendar_event_id"])


def downgrade() -> None:
    op.drop_table("meetings")
    op.drop_table("calendar_events")
    op.drop_table("sync_states")
