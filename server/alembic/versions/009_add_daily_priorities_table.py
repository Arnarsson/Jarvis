"""add daily_priorities table

Revision ID: 009
Revises: 008
Create Date: 2026-01-28
"""

from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_priorities",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index("ix_daily_priorities_date", "daily_priorities", ["date"])
    op.create_index(
        "ix_daily_priorities_date_position",
        "daily_priorities",
        ["date", "position"],
        unique=True,
    )
    op.create_index("ix_daily_priorities_created_at", "daily_priorities", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_daily_priorities_created_at", table_name="daily_priorities")
    op.drop_index("ix_daily_priorities_date_position", table_name="daily_priorities")
    op.drop_index("ix_daily_priorities_date", table_name="daily_priorities")
    op.drop_table("daily_priorities")
