import uuid
from sqlalchemy import String, Boolean, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin
import enum


class OrgPlan(str, enum.Enum):
    saas_starter = "saas_starter"
    saas_business = "saas_business"
    saas_enterprise = "saas_enterprise"
    onpremise = "onpremise"


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[OrgPlan] = mapped_column(
        SAEnum(OrgPlan), nullable=False, default=OrgPlan.saas_starter
    )
    license_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    require_2fa: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    users: Mapped[list["User"]] = relationship("User", back_populates="organization")
