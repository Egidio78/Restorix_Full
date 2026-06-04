"""Add missing FK constraints + performance indices

Revision ID: 0013_fk_and_indices
Revises: 0012_active_run_unique_index
Create Date: 2026-06-02
"""
from alembic import op
import sqlalchemy as sa

revision = '0013_fk_and_indices'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---- FK constraints mancanti ----

    # 1. servers.org_id -> organizations.id ON DELETE CASCADE
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE servers
              ADD CONSTRAINT fk_servers_org_id
              FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE;
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # 2. storage_destinations.org_id -> organizations.id
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE storage_destinations
              ADD CONSTRAINT fk_storage_destinations_org_id
              FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE;
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # 3. backup_jobs.org_id -> organizations.id
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE backup_jobs
              ADD CONSTRAINT fk_backup_jobs_org_id
              FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE;
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # 4. notification_channels.org_id -> organizations.id
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE notification_channels
              ADD CONSTRAINT fk_notification_channels_org_id
              FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE;
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # 5. backup_runs.triggered_by_user_id -> users.id ON DELETE SET NULL
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE backup_runs
              ADD CONSTRAINT fk_backup_runs_triggered_by
              FOREIGN KEY (triggered_by_user_id) REFERENCES users(id) ON DELETE SET NULL;
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # ---- Indici performance ----

    op.execute("CREATE INDEX IF NOT EXISTS ix_backup_runs_created_at ON backup_runs (created_at DESC);")

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_backup_runs_retention_candidates
        ON backup_runs (job_id, finished_at)
        WHERE status = 'success'
          AND retention_purged = false
          AND purge_abandoned = false;
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_backup_jobs_storage_destination_id ON backup_jobs (storage_destination_id);")

    op.execute("CREATE INDEX IF NOT EXISTS ix_backup_runs_parent_run_id ON backup_runs (parent_run_id) WHERE parent_run_id IS NOT NULL;")
    op.execute("CREATE INDEX IF NOT EXISTS ix_backup_runs_forwarded_to_run_id ON backup_runs (forwarded_to_run_id) WHERE forwarded_to_run_id IS NOT NULL;")

    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_logs_user_id ON audit_logs (user_id) WHERE user_id IS NOT NULL;")

    # ---- CHECK constraints ----

    op.execute("""
        DO $$ BEGIN
            ALTER TABLE backup_jobs
              ADD CONSTRAINT chk_retention_days_positive
              CHECK (retention_days > 0);
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE backup_jobs DROP CONSTRAINT IF EXISTS chk_retention_days_positive;")
    op.execute("DROP INDEX IF EXISTS ix_audit_logs_user_id;")
    op.execute("DROP INDEX IF EXISTS ix_backup_runs_forwarded_to_run_id;")
    op.execute("DROP INDEX IF EXISTS ix_backup_runs_parent_run_id;")
    op.execute("DROP INDEX IF EXISTS ix_backup_jobs_storage_destination_id;")
    op.execute("DROP INDEX IF EXISTS ix_backup_runs_retention_candidates;")
    op.execute("DROP INDEX IF EXISTS ix_backup_runs_created_at;")
    op.execute("ALTER TABLE backup_runs DROP CONSTRAINT IF EXISTS fk_backup_runs_triggered_by;")
    op.execute("ALTER TABLE notification_channels DROP CONSTRAINT IF EXISTS fk_notification_channels_org_id;")
    op.execute("ALTER TABLE backup_jobs DROP CONSTRAINT IF EXISTS fk_backup_jobs_org_id;")
    op.execute("ALTER TABLE storage_destinations DROP CONSTRAINT IF EXISTS fk_storage_destinations_org_id;")
    op.execute("ALTER TABLE servers DROP CONSTRAINT IF EXISTS fk_servers_org_id;")
