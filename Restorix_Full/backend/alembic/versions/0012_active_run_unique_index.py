"""active_run_unique_index

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-02

Fix #1: prevent duplicate pending/running BackupRun for the same job (race condition
between multiple Celery workers).  A partial unique index at the DB level is the
only reliable guard — application-level checks are not atomic.
"""
from alembic import op

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE UNIQUE INDEX uq_one_active_run_per_job
        ON backup_runs (job_id)
        WHERE status IN ('pending', 'running')
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_one_active_run_per_job")
