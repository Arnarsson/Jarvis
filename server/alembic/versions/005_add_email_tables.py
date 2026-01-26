"""add email tables

Revision ID: 005
Revises: 004
Create Date: 2026-01-25
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Email sync state table
    op.create_table(
        "email_sync_states",
        sa.Column("id", sa.String(50), nullable=False),
        sa.Column("history_id", sa.String(50), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # Email messages table
    op.create_table(
        "email_messages",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("gmail_message_id", sa.String(100), nullable=False),
        sa.Column("thread_id", sa.String(100), nullable=False),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("from_address", sa.String(200), nullable=True),
        sa.Column("from_name", sa.String(200), nullable=True),
        sa.Column("to_addresses", sa.Text(), nullable=True),
        sa.Column("cc_addresses", sa.Text(), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=True),
        sa.Column("date_sent", sa.DateTime(timezone=True), nullable=False),
        sa.Column("date_received", sa.DateTime(timezone=True), nullable=True),
        sa.Column("labels_json", sa.Text(), nullable=True),
        sa.Column("is_unread", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_important", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("processing_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("gmail_message_id"),
    )

    # Indexes
    op.create_index("ix_email_messages_date_sent", "email_messages", ["date_sent"])
    op.create_index("ix_email_messages_gmail_id", "email_messages", ["gmail_message_id"])
    op.create_index("ix_email_messages_from", "email_messages", ["from_address"])
    op.create_index("ix_email_messages_thread", "email_messages", ["thread_id"])


def downgrade() -> None:
    op.drop_index("ix_email_messages_thread", "email_messages")
    op.drop_index("ix_email_messages_from", "email_messages")
    op.drop_index("ix_email_messages_gmail_id", "email_messages")
    op.drop_index("ix_email_messages_date_sent", "email_messages")
    op.drop_table("email_messages")
    op.drop_table("email_sync_states")
