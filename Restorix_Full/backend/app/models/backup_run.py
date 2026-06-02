import uuid
from datetime import datetime
from sqlalchemy import String, Text, BigInteger, DateTime, ForeignKey, Boolean, Integer, Enum as SAEnum, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin
import enum


class RunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    success = "success"
    failed = "failed"
    cancelled = "cancelled"


class TriggerType(str, enum.Enum):
    scheduler = "scheduler"
    manual = "manual"
    forwarded = "forwarded"


class BackupRun(Base, TimestampMixin):
    __tablename__ = "backup_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("backup_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[RunStatus] = mapped_column(
        SAEnum(RunStatus, name="runstatus", create_type=False),
        nullable=False,
        default=RunStatus.pending,
    )
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_type: Mapped[TriggerType] = mapped_column(
        SAEnum(TriggerType, name="triggertype", create_type=False),
        nullable=False,
        default=TriggerType.manual,
    )
    triggered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    retention_purged: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    retention_purged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retention_purge_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    retention_purge_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    purge_abandoned: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    parent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("backup_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    forwarded_to_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("backup_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    job: Mapped["BackupJob"] = relationship("BackupJob", back_populates="runs")
