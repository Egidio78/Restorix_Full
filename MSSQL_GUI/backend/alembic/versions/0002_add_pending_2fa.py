"""add pending_two_fa_secret_enc to users

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("pending_two_fa_secret_enc", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("users", "pending_two_fa_secret_enc")
