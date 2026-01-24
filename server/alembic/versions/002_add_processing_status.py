"""Add processing_status to captures table.

Revision ID: 002
Revises: 001
Create Date: 2026-01-24
"""

from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "captures",
        sa.Column("processing_status", sa.String(20), nullable=False, server_default="pending"),
    )
    op.create_index(
        "ix_captures_processing_status",
        "captures",
        ["processing_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_captures_processing_status", table_name="captures")
    op.drop_column("captures", "processing_status")
