"""contact_extractions: status, model, evidence, error

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing (Step 2 sample) rows were successful extractions.
    op.add_column(
        "contact_extractions",
        sa.Column("status", sa.String(16), nullable=False, server_default="succeeded"),
    )
    op.add_column("contact_extractions", sa.Column("model", sa.String(64), nullable=True))
    op.add_column("contact_extractions", sa.Column("evidence", postgresql.JSONB(), nullable=True))
    op.add_column("contact_extractions", sa.Column("error_code", sa.String(64), nullable=True))
    op.add_column("contact_extractions", sa.Column("error", sa.Text(), nullable=True))


def downgrade() -> None:
    for column in ("error", "error_code", "evidence", "model", "status"):
        op.drop_column("contact_extractions", column)
