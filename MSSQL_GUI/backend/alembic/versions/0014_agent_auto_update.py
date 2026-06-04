"""Add agent auto-update fields to servers table.

Revision ID: 0014_agent_auto_update
Revises: 0013_fk_and_indices
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa


revision = '0014_agent_auto_update'
down_revision = '0013_fk_and_indices'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('servers', sa.Column('auto_update', sa.Boolean(), nullable=False, server_default=sa.text('true')))
    op.add_column('servers', sa.Column('update_pending', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('servers', sa.Column('last_update_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('servers', sa.Column('last_update_status', sa.String(length=20), nullable=True))
    op.add_column('servers', sa.Column('last_update_error', sa.Text(), nullable=True))
    op.add_column('servers', sa.Column('last_update_from_version', sa.String(length=50), nullable=True))
    op.add_column('servers', sa.Column('last_update_to_version', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('servers', 'last_update_to_version')
    op.drop_column('servers', 'last_update_from_version')
    op.drop_column('servers', 'last_update_error')
    op.drop_column('servers', 'last_update_status')
    op.drop_column('servers', 'last_update_at')
    op.drop_column('servers', 'update_pending')
    op.drop_column('servers', 'auto_update')
