import uuid
from sqlalchemy import String, Boolean, ForeignKey, Enum as SAEnum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin
import enum


class UserRole(str, enum.Enum):
    superadmin = "superadmin"
    admin = "admin"
    operator = "operator"
    viewer = "viewer"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="userrole", create_type=False), nullable=False, default=UserRole.viewer
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # 2FA
    two_fa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    two_fa_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    two_fa_backup_codes_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    pending_two_fa_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="users")
