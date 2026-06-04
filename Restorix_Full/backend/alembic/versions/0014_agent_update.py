"""Agent auto-update: update_requested flag on servers

Revision ID: 0014_agent_update
Revises: 0013_fk_and_indices
Create Date: 2026-06-04
"""
from alembic import op
import sqlalchemy as sa

revision = '0014_agent_update'
down_revision = '0013_fk_and_indices'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'servers',
        sa.Column('update_requested', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )


def downgrade() -> None:
    op.drop_column('servers', 'update_requested')
