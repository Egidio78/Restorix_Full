"""MySQL backup: optional exclude-tables glob patterns

Revision ID: 0016_mysql_exclude_tables
Revises: 0015_agent_update_status
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = '0016_mysql_exclude_tables'
down_revision = '0015_agent_update_status'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'backup_jobs',
        sa.Column('mysql_exclude_tables', sa.String(1000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('backup_jobs', 'mysql_exclude_tables')
