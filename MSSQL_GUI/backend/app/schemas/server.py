import uuid
from datetime import datetime
from pydantic import BaseModel
from app.models.server import AgentStatus


class ServerCreate(BaseModel):
    name: str
    hostname: str


class ServerOut(BaseModel):
    id: uuid.UUID
    name: str
    hostname: str
    agent_token: str
    agent_version: str | None
    status: AgentStatus
    is_active: bool

    # Agent auto-update (migration 0014)
    auto_update: bool = True
    update_pending: bool = False
    last_update_at: datetime | None = None
    last_update_status: str | None = None
    last_update_error: str | None = None
    last_update_from_version: str | None = None
    last_update_to_version: str | None = None

    model_config = {"from_attributes": True}


class DbInstanceCreate(BaseModel):
    name: str
    mssql_instance: str
    username: str | None = None
    password: str | None = None


class DbInstanceOut(BaseModel):
    id: uuid.UUID
    server_id: uuid.UUID
    name: str
    mssql_instance: str
    is_active: bool

    model_config = {"from_attributes": True}
