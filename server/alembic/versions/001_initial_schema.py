"""Initial schema with captures table.

Revision ID: 001_initial
Revises:
Create Date: 2026-01-24

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create captures table."""
    op.create_table(
        "captures",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("filepath", sa.String(500), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("monitor_index", sa.Integer, default=0),
        sa.Column("width", sa.Integer, nullable=False),
        sa.Column("height", sa.Integer, nullable=False),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("ocr_text", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # Create index on timestamp for time-range queries
    op.create_index("ix_captures_timestamp", "captures", ["timestamp"])


def downgrade() -> None:
    """Drop captures table."""
    op.drop_index("ix_captures_timestamp", table_name="captures")
    op.drop_table("captures")
