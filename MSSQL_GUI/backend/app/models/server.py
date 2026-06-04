import uuid
import secrets
from datetime import datetime
from sqlalchemy import String, Enum as SAEnum, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin
import enum


class AgentStatus(str, enum.Enum):
    never_connected = "never_connected"
    online = "online"
    offline = "offline"


class Server(Base, TimestampMixin):
    __tablename__ = "servers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    # TODO: hash storage in v1.5.x — attualmente agent_token e' plain text nel DB.
    # Breaking change per agenti gia' deployati: richiede schema migration + token rotation.
    agent_token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True,
        default=lambda: secrets.token_hex(32)
    )
    agent_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[AgentStatus] = mapped_column(
        SAEnum(AgentStatus, name="agentstatus", create_type=False),
        nullable=False,
        default=AgentStatus.never_connected,
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    last_heartbeat_endpoint: Mapped[str | None] = mapped_column(String(512), nullable=True)
    endpoint_version_seen: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # ── Agent auto-update (migration 0014) ─────────────────
    auto_update: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    update_pending: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    last_update_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_update_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    last_update_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_update_from_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_update_to_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # OS tracking (migration 0015)
    os_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(255), nullable=True)

    db_instances: Mapped[list["DbInstance"]] = relationship(
        "DbInstance", back_populates="server", cascade="all, delete-orphan"
    )
    backup_jobs: Mapped[list["BackupJob"]] = relationship(
        "BackupJob", back_populates="server"
    )
