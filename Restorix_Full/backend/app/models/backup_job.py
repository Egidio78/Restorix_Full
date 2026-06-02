import uuid
import enum
from sqlalchemy import String, Boolean, Integer, ForeignKey, Enum as SAEnum, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin


class BackupType(str, enum.Enum):
    mssql = "mssql"
    folder = "folder"
    mysql = "mysql"


class BackupJob(Base, TimestampMixin):
    __tablename__ = "backup_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    backup_type: Mapped[BackupType] = mapped_column(
        SAEnum(BackupType, name="backuptype", create_type=False),
        nullable=False,
        default=BackupType.mssql,
    )
    db_instance_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("db_instances.id", ondelete="CASCADE"), nullable=True
    )
    folder_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    storage_destination_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("storage_destinations.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    schedule_cron: Mapped[str] = mapped_column(String(100), nullable=False)
    compression_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    mssql_native_compression: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"), default=True)
    encryption_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    encryption_password_enc: Mapped[str | None] = mapped_column(String(500), nullable=True)
    retention_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)

    server: Mapped["Server"] = relationship("Server", back_populates="backup_jobs")
    db_instance: Mapped["DbInstance"] = relationship("DbInstance", back_populates="backup_jobs")
    storage_destination: Mapped["StorageDestination"] = relationship(
        "StorageDestination", back_populates="backup_jobs"
    )
    runs: Mapped[list["BackupRun"]] = relationship(
        "BackupRun", back_populates="job", cascade="all, delete-orphan"
    )

    @property
    def database_name(self) -> str | None:
        """Name of the linked DbInstance, or None. Safe: returns None if the
        relationship was not eager-loaded (avoids async lazy-load errors)."""
        from sqlalchemy import inspect as _sa_inspect
        if "db_instance" in _sa_inspect(self).unloaded:
            return None
        return self.db_instance.name if self.db_instance else None
