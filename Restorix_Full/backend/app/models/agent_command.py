import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models.base import Base


# Whitelisted actions the agent will execute. Anything else is rejected.
AGENT_ACTIONS = {
    "healthcheck",     # report version/OS/deps/disk/connectivity (non-root)
    "collect_logs",    # return recent agent.log lines (non-root)
    "test_db",         # test a DB connection (non-root)
    "set_config",      # change poll interval / log level / temp dir (non-root)
    "install_deps",    # install mysqldump / sqlcmd / clients (root)
    "restart_agent",   # restart the systemd service (root)
    "repair",          # re-run bootstrap, reinstall package if needed (root)
}

ROOT_ACTIONS = {"install_deps", "restart_agent", "repair"}


class AgentCommand(Base):
    __tablename__ = "agent_commands"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
