"""Add ui_theme to organizations

Revision ID: 0008_ui_theme
Revises: 0007_mssql_native
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa


revision = "0008_ui_theme"
down_revision = "0007_mssql_native"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("ui_theme", sa.String(length=20), nullable=False, server_default=sa.text("'dark'")),
    )


def downgrade() -> None:
    op.drop_column("organizations", "ui_theme")
