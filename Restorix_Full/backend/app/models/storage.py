import uuid
from datetime import datetime
from sqlalchemy import String, Text, Boolean, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin
import enum


class StorageType(str, enum.Enum):
    s3 = "s3"
    ftp = "ftp"
    ftps = "ftps"
    sftp = "sftp"
    gdrive = "gdrive"
    onedrive = "onedrive"
    nextcloud = "nextcloud"
    webdav = "webdav"


class StorageDestination(Base, TimestampMixin):
    __tablename__ = "storage_destinations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_type: Mapped[StorageType] = mapped_column(
        SAEnum(StorageType, name="storagetype", create_type=False),
        nullable=False,
    )
    config_enc: Mapped[str] = mapped_column(Text, nullable=False)
    last_tested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    backup_jobs: Mapped[list["BackupJob"]] = relationship(
        "BackupJob", back_populates="storage_destination"
    )
