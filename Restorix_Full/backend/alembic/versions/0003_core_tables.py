"""core tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import ENUM as PGEnum

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE agentstatus AS ENUM ('never_connected', 'online', 'offline');
        EXCEPTION WHEN duplicate_object THEN null; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE storagetype AS ENUM ('s3', 'ftp', 'ftps', 'sftp', 'gdrive', 'onedrive', 'nextcloud', 'webdav');
        EXCEPTION WHEN duplicate_object THEN null; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE runstatus AS ENUM ('pending', 'running', 'success', 'failed', 'cancelled');
        EXCEPTION WHEN duplicate_object THEN null; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE triggertype AS ENUM ('scheduler', 'manual');
        EXCEPTION WHEN duplicate_object THEN null; END $$
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE channeltype AS ENUM ('email', 'webhook');
        EXCEPTION WHEN duplicate_object THEN null; END $$
    """)

    agentstatus = PGEnum("never_connected", "online", "offline", name="agentstatus", create_type=False)
    storagetype = PGEnum("s3", "ftp", "ftps", "sftp", "gdrive", "onedrive", "nextcloud", "webdav", name="storagetype", create_type=False)
    runstatus = PGEnum("pending", "running", "success", "failed", "cancelled", name="runstatus", create_type=False)
    triggertype = PGEnum("scheduler", "manual", name="triggertype", create_type=False)
    channeltype = PGEnum("email", "webhook", name="channeltype", create_type=False)

    op.create_table(
        "servers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("hostname", sa.String(255), nullable=False),
        sa.Column("agent_token", sa.String(64), unique=True, nullable=False),
        sa.Column("agent_version", sa.String(50), nullable=True),
        sa.Column("status", agentstatus, nullable=False, server_default="never_connected"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_servers_org_id", "servers", ["org_id"])
    op.create_index("ix_servers_agent_token", "servers", ["agent_token"])

    op.create_table(
        "db_instances",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("server_id", UUID(as_uuid=True), sa.ForeignKey("servers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("mssql_instance", sa.String(255), nullable=False),
        sa.Column("credentials_enc", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_db_instances_server_id", "db_instances", ["server_id"])

    op.create_table(
        "storage_destinations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("storage_type", storagetype, nullable=False),
        sa.Column("config_enc", sa.Text, nullable=False),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_ok", sa.Boolean, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_storage_destinations_org_id", "storage_destinations", ["org_id"])

    op.create_table(
        "backup_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), nullable=False),
        sa.Column("server_id", UUID(as_uuid=True), sa.ForeignKey("servers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("db_instance_id", UUID(as_uuid=True), sa.ForeignKey("db_instances.id", ondelete="CASCADE"), nullable=False),
        sa.Column("storage_destination_id", UUID(as_uuid=True), sa.ForeignKey("storage_destinations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("schedule_cron", sa.String(100), nullable=False),
        sa.Column("compression_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("encryption_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("encryption_password_enc", sa.String(500), nullable=True),
        sa.Column("retention_days", sa.Integer, nullable=False, server_default="30"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_backup_jobs_org_id", "backup_jobs", ["org_id"])
    op.create_index("ix_backup_jobs_server_id", "backup_jobs", ["server_id"])

    op.create_table(
        "backup_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("backup_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", runstatus, nullable=False, server_default="pending"),
        sa.Column("size_bytes", sa.BigInteger, nullable=True),
        sa.Column("file_path", sa.String(1000), nullable=True),
        sa.Column("checksum_sha256", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("trigger_type", triggertype, nullable=False, server_default="manual"),
        sa.Column("triggered_by_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_backup_runs_job_id", "backup_runs", ["job_id"])

    op.create_table(
        "notification_channels",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("channel_type", channeltype, nullable=False),
        sa.Column("config_enc", sa.Text, nullable=False),
        sa.Column("on_success", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("on_failure", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_notification_channels_org_id", "notification_channels", ["org_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_id", UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=True),
        sa.Column("target_id", UUID(as_uuid=True), nullable=True),
        sa.Column("metadata_json", sa.Text, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_org_id", "audit_logs", ["org_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("notification_channels")
    op.drop_table("backup_runs")
    op.drop_table("backup_jobs")
    op.drop_table("storage_destinations")
    op.drop_table("db_instances")
    op.drop_table("servers")
    op.execute("DROP TYPE IF EXISTS channeltype")
    op.execute("DROP TYPE IF EXISTS triggertype")
    op.execute("DROP TYPE IF EXISTS runstatus")
    op.execute("DROP TYPE IF EXISTS storagetype")
    op.execute("DROP TYPE IF EXISTS agentstatus")
