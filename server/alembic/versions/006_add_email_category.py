"""add email category column

Revision ID: 006
Revises: 005
Create Date: 2026-01-26
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "email_messages",
        sa.Column("category", sa.String(20), nullable=True),
    )
    op.create_index("ix_email_messages_category", "email_messages", ["category"])


def downgrade() -> None:
    op.drop_index("ix_email_messages_category", "email_messages")
    op.drop_column("email_messages", "category")
