import uuid
from typing import Any
from pydantic import BaseModel
from app.models.notification import ChannelType


class NotificationChannelCreate(BaseModel):
    name: str
    channel_type: ChannelType
    config: dict[str, Any]   # plain config, will be encrypted
    on_success: bool = True
    on_failure: bool = True
    enabled: bool = True


class NotificationChannelOut(BaseModel):
    id: uuid.UUID
    name: str
    channel_type: ChannelType
    on_success: bool
    on_failure: bool
    enabled: bool

    model_config = {"from_attributes": True}
