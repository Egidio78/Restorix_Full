"""Add parent_run_id + forwarded_to_run_id to backup_runs + 'forwarded' trigger

Revision ID: 0009_forward_runs
Revises: 0008_ui_theme
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa


revision = "0009_forward_runs"
down_revision = "0008_ui_theme"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # New columns
    op.add_column("backup_runs", sa.Column("parent_run_id", sa.UUID(), nullable=True))
    op.add_column("backup_runs", sa.Column("forwarded_to_run_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_backup_runs_parent_run_id",
        "backup_runs", "backup_runs",
        ["parent_run_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_backup_runs_forwarded_to_run_id",
        "backup_runs", "backup_runs",
        ["forwarded_to_run_id"], ["id"],
        ondelete="SET NULL",
    )
    # Extend trigger enum — ALTER TYPE ADD VALUE must run outside a transaction in Postgres
    conn = op.get_bind()
    conn.execute(sa.text("COMMIT"))
    conn.execute(sa.text("ALTER TYPE triggertype ADD VALUE IF NOT EXISTS 'forwarded'"))
    conn.execute(sa.text("BEGIN"))


def downgrade() -> None:
    op.drop_constraint("fk_backup_runs_forwarded_to_run_id", "backup_runs", type_="foreignkey")
    op.drop_constraint("fk_backup_runs_parent_run_id", "backup_runs", type_="foreignkey")
    op.drop_column("backup_runs", "forwarded_to_run_id")
    op.drop_column("backup_runs", "parent_run_id")
    # NOTE: postgres doesn't support DROP VALUE on enum; 'forwarded' stays
