import uuid
from datetime import datetime
from typing import Any
from pydantic import BaseModel
from app.models.storage import StorageType


class StorageCreate(BaseModel):
    name: str
    storage_type: StorageType
    config: dict[str, Any]  # plain config, will be encrypted server-side


class StorageOut(BaseModel):
    id: uuid.UUID
    name: str
    storage_type: StorageType
    last_tested_at: datetime | None = None
    last_test_ok: bool | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class StorageTestResult(BaseModel):
    ok: bool
    message: str
