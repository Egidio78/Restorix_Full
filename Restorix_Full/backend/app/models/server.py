import uuid
import secrets
from sqlalchemy import String, Enum as SAEnum
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
    engine: Mapped[str] = mapped_column(String(20), nullable=False, default="mssql")
    agent_token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True,
        default=lambda: secrets.token_hex(32)
    )
    agent_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    update_requested: Mapped[bool] = mapped_column(default=False, nullable=False)
    status: Mapped[AgentStatus] = mapped_column(
        SAEnum(AgentStatus, name="agentstatus", create_type=False),
        nullable=False,
        default=AgentStatus.never_connected,
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    db_instances: Mapped[list["DbInstance"]] = relationship(
        "DbInstance", back_populates="server", cascade="all, delete-orphan"
    )
    backup_jobs: Mapped[list["BackupJob"]] = relationship(
        "BackupJob", back_populates="server"
    )

    @property
    def latest_version(self) -> str:
        from app.core.agent_release import LATEST_AGENT_VERSION
        return LATEST_AGENT_VERSION

    @property
    def update_available(self) -> bool:
        from app.core.agent_release import LATEST_AGENT_VERSION
        return bool(self.agent_version) and self.agent_version != LATEST_AGENT_VERSION
