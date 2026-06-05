"""Remote agent management: agent_commands queue

Revision ID: 0017_agent_commands
Revises: 0016_mysql_exclude_tables
Create Date: 2026-06-06
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = '0017_agent_commands'
down_revision = '0016_mysql_exclude_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'agent_commands',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('server_id', UUID(as_uuid=True),
                  sa.ForeignKey('servers.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('action', sa.String(40), nullable=False),
        sa.Column('params', JSONB, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('result', sa.Text, nullable=True),
        sa.Column('created_by_user_id', UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    )
    # fast lookup of the next pending command per server
    op.execute("""
        CREATE INDEX ix_agent_commands_pending
        ON agent_commands (server_id, created_at)
        WHERE status = 'pending'
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_agent_commands_pending")
    op.drop_table('agent_commands')
