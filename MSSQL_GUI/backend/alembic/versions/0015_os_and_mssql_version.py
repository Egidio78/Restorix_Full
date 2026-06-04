"""Track server OS + MSSQL version metadata.

Revision ID: 0015_os_and_mssql_version
Revises: 0014_agent_auto_update
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = '0015_os_and_mssql_version'
down_revision = '0014_agent_auto_update'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('servers', sa.Column('os_type', sa.String(20), nullable=True))
    op.add_column('servers', sa.Column('os_version', sa.String(255), nullable=True))

    op.add_column('db_instances', sa.Column('mssql_version', sa.String(255), nullable=True))
    op.add_column('db_instances', sa.Column('mssql_product_version_string', sa.String(500), nullable=True))
    op.add_column('db_instances', sa.Column('mssql_edition', sa.String(100), nullable=True))
    op.add_column('db_instances', sa.Column('mssql_product_level', sa.String(50), nullable=True))
    op.add_column('db_instances', sa.Column('metadata_updated_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('db_instances', 'metadata_updated_at')
    op.drop_column('db_instances', 'mssql_product_level')
    op.drop_column('db_instances', 'mssql_edition')
    op.drop_column('db_instances', 'mssql_product_version_string')
    op.drop_column('db_instances', 'mssql_version')
    op.drop_column('servers', 'os_version')
    op.drop_column('servers', 'os_type')
