"""add email archived flag

Revision ID: 007
Revises: 006
Create Date: 2026-01-28
"""

from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_messages",
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_email_messages_archived", "email_messages", ["is_archived"])


def downgrade() -> None:
    op.drop_index("ix_email_messages_archived", "email_messages")
    op.drop_column("email_messages", "is_archived")
