"""Schemas for agent heartbeat protocol v2.

v1.0.x agents POST with empty body + ?agent_version=... query param.
v1.4+ agents POST JSON body and consume the canonical_endpoint response.
All body fields are optional to preserve backward compatibility.
"""
from pydantic import BaseModel


class HeartbeatPayload(BaseModel):
    """Heartbeat v2 request body (agent v1.4+). All fields optional."""
    agent_version: str | None = None
    uptime_seconds: int | None = None
    current_endpoint: str | None = None  # URL the agent is currently calling


class HeartbeatResponse(BaseModel):
    """Heartbeat v2 response. v1.0.x agents simply ignore the extra fields."""
    status: str
    server_id: str
    next_poll_seconds: int
    canonical_endpoint: str
    endpoint_version: str
    # Agent auto-update (Piano 8 / migration 0014). All nullable for backward compat.
    update_command: str | None = None
    download_url: str | None = None
    expected_sha256: str | None = None
