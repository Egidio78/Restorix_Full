from datetime import datetime
from uuid import UUID
from typing import Any
from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: UUID
    org_id: UUID | None
    user_id: UUID | None
    user_email: str | None = None
    action: str
    target_type: str | None
    target_id: str | None
    description: str = ''
    metadata: dict[str, Any] = {}
    ip_address: str | None
    user_agent: str | None = None
    created_at: datetime


class AuditListResponse(BaseModel):
    items: list[AuditLogOut]
    total: int
    page: int
    page_size: int
