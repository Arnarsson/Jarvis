"""Add conversations table for imported AI chats.

Revision ID: 003
Revises: 002
Create Date: 2026-01-24
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("full_text", sa.Text, nullable=False),
        sa.Column("message_count", sa.Integer, nullable=False),
        sa.Column("conversation_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("processing_status", sa.String(20), nullable=False, server_default="pending"),
    )

    op.create_index("ix_conversations_source", "conversations", ["source"])
    op.create_index("ix_conversations_date", "conversations", ["conversation_date"])
    op.create_index(
        "ix_conversations_external_id",
        "conversations",
        ["external_id", "source"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_table("conversations")
