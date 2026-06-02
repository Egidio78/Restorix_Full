import uuid
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
