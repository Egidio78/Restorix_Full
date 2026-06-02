import uuid
from sqlalchemy import String, Boolean, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin
import enum


class ChannelType(str, enum.Enum):
    email = "email"
    webhook = "webhook"


class NotificationChannel(Base, TimestampMixin):
    __tablename__ = "notification_channels"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    channel_type: Mapped[ChannelType] = mapped_column(
        SAEnum(ChannelType, name="channeltype", create_type=False),
        nullable=False,
    )
    config_enc: Mapped[str] = mapped_column(Text, nullable=False)
    on_success: Mapped[bool] = mapped_column(default=True, nullable=False)
    on_failure: Mapped[bool] = mapped_column(default=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
