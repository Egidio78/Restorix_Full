"""Agent auto-update v2: auto_update_enabled + update_status

Revision ID: 0015_agent_update_status
Revises: 0014_agent_update
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = '0015_agent_update_status'
down_revision = '0014_agent_update'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'servers',
        sa.Column('auto_update_enabled', sa.Boolean(), nullable=False, server_default=sa.text('true')),
    )
    op.add_column(
        'servers',
        sa.Column('update_status', sa.String(20), nullable=False, server_default='idle'),
    )


def downgrade() -> None:
    op.drop_column('servers', 'update_status')
    op.drop_column('servers', 'auto_update_enabled')
