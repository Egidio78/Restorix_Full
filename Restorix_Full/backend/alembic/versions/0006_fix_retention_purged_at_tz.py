"""Fix retention_purged_at to TIMESTAMPTZ

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "backup_runs",
        "retention_purged_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="retention_purged_at AT TIME ZONE 'UTC'",
    )


def downgrade() -> None:
    op.alter_column(
        "backup_runs",
        "retention_purged_at",
        type_=sa.DateTime(timezone=False),
    )
