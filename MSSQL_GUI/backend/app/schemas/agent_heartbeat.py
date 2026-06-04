"""Schemas for agent heartbeat protocol v2.

v1.0.x agents POST with empty body + ?agent_version=... query param.
v1.4+ agents POST JSON body and consume the canonical_endpoint response.
All body fields are optional to preserve backward compatibility.
"""
import uuid
from pydantic import BaseModel, Field, field_validator

_ALLOWED_OS_TYPES = {"linux", "windows", "unknown"}


def _validate_os_version(v):
    if v is None:
        return None
    if len(v) > 255:
        raise ValueError("os_version exceeds 255 characters")
    if "\x00" in v or "\n" in v or "\r" in v:
        raise ValueError("os_version contains forbidden control characters")
    return v


class HeartbeatPayload(BaseModel):
    """Heartbeat v2 request body (agent v1.4+). All fields optional."""
    agent_version: str | None = None
    uptime_seconds: int | None = None
    current_endpoint: str | None = None  # URL the agent is currently calling
    # OS tracking (v3 / migration 0015) — backward compatible
    os_type: str | None = None
    os_version: str | None = None

    @field_validator("os_type")
    @classmethod
    def _check_os_type(cls, v):
        if v is None:
            return None
        if v not in _ALLOWED_OS_TYPES:
            raise ValueError(f"os_type must be one of {sorted(_ALLOWED_OS_TYPES)}")
        return v

    @field_validator("os_version")
    @classmethod
    def _check_os_version(cls, v):
        return _validate_os_version(v)


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


class DbInstanceMetadataPayload(BaseModel):
    """Body for POST /agent/dbinstance-metadata."""
    db_instance_id: uuid.UUID
    mssql_version: str | None = Field(default=None, max_length=255)
    mssql_product_version_string: str | None = Field(default=None, max_length=500)
    mssql_edition: str | None = Field(default=None, max_length=100)
    mssql_product_level: str | None = Field(default=None, max_length=50)

    @field_validator("mssql_version", "mssql_product_version_string", "mssql_edition", "mssql_product_level")
    @classmethod
    def _no_null_bytes(cls, v):
        if v is None:
            return None
        if "\x00" in v:
            raise ValueError("null byte forbidden")
        return v.strip()
