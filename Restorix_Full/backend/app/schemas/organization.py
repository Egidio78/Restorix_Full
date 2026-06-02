import uuid
from pydantic import BaseModel, Field, field_validator
from croniter import croniter


class OrganizationSettingsUpdate(BaseModel):
    audit_retention_days: int | None = Field(default=None, ge=90, le=3650)
    schedule_cleanup_cron: str | None = Field(default=None, max_length=100)
    require_2fa: bool | None = None
    restore_temp_dir: str | None = Field(default=None, max_length=500)
    ui_theme: str | None = Field(default=None, max_length=20)

    @field_validator("ui_theme")
    @classmethod
    def validate_ui_theme(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in ("dark", "light"):
            raise ValueError("ui_theme must be 'dark' or 'light'")
        return v

    @field_validator("schedule_cleanup_cron")
    @classmethod
    def validate_cron(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not croniter.is_valid(v):
            raise ValueError("Invalid cron expression")
        return v

    @field_validator("restore_temp_dir")
    @classmethod
    def validate_temp_dir(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if ".." in v:
            raise ValueError("Path traversal not allowed")
        if not v.startswith("/"):
            raise ValueError("Must be absolute path")
        return v


class OrganizationSettingsOut(BaseModel):
    id: uuid.UUID
    audit_retention_days: int
    schedule_cleanup_cron: str
    require_2fa: bool
    restore_temp_dir: str
    ui_theme: str

    model_config = {"from_attributes": True}


class VerifyTempdirRequest(BaseModel):
    path: str = Field(..., max_length=500)


class VerifyTempdirResponse(BaseModel):
    ok: bool
    free_gb: float | None = None
    message: str
