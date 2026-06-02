"""add backup_type and folder_path to backup_jobs

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-31
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE TYPE backuptype AS ENUM ('mssql', 'folder')")
    op.add_column("backup_jobs", sa.Column(
        "backup_type",
        sa.Enum("mssql", "folder", name="backuptype", create_type=False),
        nullable=False,
        server_default="mssql",
    ))
    op.add_column("backup_jobs", sa.Column("folder_path", sa.String(1000), nullable=True))
    op.alter_column("backup_jobs", "db_instance_id", nullable=True)


def downgrade() -> None:
    op.alter_column("backup_jobs", "db_instance_id", nullable=False)
    op.drop_column("backup_jobs", "folder_path")
    op.drop_column("backup_jobs", "backup_type")
    op.execute("DROP TYPE IF EXISTS backuptype")
