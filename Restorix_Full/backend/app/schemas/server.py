import uuid
from pydantic import BaseModel
from app.models.server import AgentStatus


class ServerCreate(BaseModel):
    name: str
    hostname: str
    engine: str = "mssql"


class ServerOut(BaseModel):
    id: uuid.UUID
    name: str
    hostname: str
    engine: str = "mssql"
    agent_token: str
    agent_version: str | None
    status: AgentStatus
    is_active: bool
    update_requested: bool = False
    auto_update_enabled: bool = True
    update_status: str = "idle"
    latest_version: str = ""
    update_available: bool = False
    update_badge: str = "unknown"

    model_config = {"from_attributes": True}


class DbInstanceCreate(BaseModel):
    name: str
    connection_string: str
    username: str | None = None
    password: str | None = None


class DbInstanceOut(BaseModel):
    id: uuid.UUID
    server_id: uuid.UUID
    name: str
    connection_string: str
    is_active: bool

    model_config = {"from_attributes": True}
