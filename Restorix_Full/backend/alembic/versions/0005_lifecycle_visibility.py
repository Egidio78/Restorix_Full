"""Piano 5: lifecycle & visibility — retention + audit + restore tempdir

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("backup_runs", sa.Column("retention_purged", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("backup_runs", sa.Column("retention_purged_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("backup_runs", sa.Column("retention_purge_error", sa.Text(), nullable=True))
    op.add_column("backup_runs", sa.Column("retention_purge_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")))
    op.add_column("backup_runs", sa.Column("purge_abandoned", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("organizations", sa.Column("audit_retention_days", sa.Integer(), nullable=False, server_default=sa.text("365")))
    op.add_column("organizations", sa.Column("schedule_cleanup_cron", sa.String(length=100), nullable=False, server_default=sa.text("'0 3 * * *'")))
    op.add_column("organizations", sa.Column("restore_temp_dir", sa.String(length=500), nullable=False, server_default=sa.text("'/var/lib/dbshield/restore-tmp'")))
    # NOTE: audit_logs uses "action" column (no "event_type"); index name kept per plan for traceability
    op.create_index("ix_audit_log_org_created_event", "audit_logs", ["org_id", sa.text("created_at DESC"), "action"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_org_created_event", table_name="audit_logs")
    op.drop_column("organizations", "restore_temp_dir")
    op.drop_column("organizations", "schedule_cleanup_cron")
    op.drop_column("organizations", "audit_retention_days")
    op.drop_column("backup_runs", "purge_abandoned")
    op.drop_column("backup_runs", "retention_purge_attempts")
    op.drop_column("backup_runs", "retention_purge_error")
    op.drop_column("backup_runs", "retention_purged_at")
    op.drop_column("backup_runs", "retention_purged")
