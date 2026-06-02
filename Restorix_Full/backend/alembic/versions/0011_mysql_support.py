"""mysql_support

Revision ID: 0011
Revises: 0009_forward_runs
Create Date: 2026-06-02

"""
from alembic import op
import sqlalchemy as sa

revision = '0011'
down_revision = '0009_forward_runs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Aggiunge engine a servers (default 'mssql' per backward compat)
    op.add_column('servers', sa.Column('engine', sa.String(20), nullable=False, server_default='mssql'))

    # Rinomina mssql_instance → connection_string in db_instances
    op.alter_column('db_instances', 'mssql_instance', new_column_name='connection_string')

    # Aggiunge valore 'mysql' all'enum backuptype (non distruttivo in Postgres)
    op.execute("ALTER TYPE backuptype ADD VALUE IF NOT EXISTS 'mysql'")


def downgrade() -> None:
    op.alter_column('db_instances', 'connection_string', new_column_name='mssql_instance')
    op.drop_column('servers', 'engine')
    # Nota: non si può rimuovere un valore da un enum Postgres senza ricreare il tipo
