from uuid import UUID
from pydantic import BaseModel, Field


class ForwardRequest(BaseModel):
    target_storage_id: UUID
    mode: str = Field(..., pattern="^(copy|move)$")


class ForwardResponse(BaseModel):
    status: str = "accepted"
    task_id: str
    shadow_run_id: UUID
