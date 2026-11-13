"""create uploads

Revision ID: 0001
Revises:
Create Date: 2026-11-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "uploads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column(
            "hubspot_status",
            sa.Enum(
                "pending",
                "uploaded",
                "failed",
                "skipped",
                name="hubspot_status",
                native_enum=False,
                length=16,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("hubspot_file_id", sa.String(64), nullable=True),
        sa.Column("hubspot_url", sa.Text(), nullable=True),
        sa.Column("hubspot_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_uploads_sha256", "uploads", ["sha256"])


def downgrade() -> None:
    op.drop_index("ix_uploads_sha256", table_name="uploads")
    op.drop_table("uploads")
