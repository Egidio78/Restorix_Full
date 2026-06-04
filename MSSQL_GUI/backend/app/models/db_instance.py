import uuid
from datetime import datetime
from sqlalchemy import String, ForeignKey, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin


class DbInstance(Base, TimestampMixin):
    __tablename__ = "db_instances"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    mssql_instance: Mapped[str] = mapped_column(String(255), nullable=False)
    credentials_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    # MSSQL metadata (migration 0015)
    mssql_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mssql_product_version_string: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mssql_edition: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mssql_product_level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    metadata_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    server: Mapped["Server"] = relationship("Server", back_populates="db_instances")
    backup_jobs: Mapped[list["BackupJob"]] = relationship(
        "BackupJob", back_populates="db_instance"
    )
