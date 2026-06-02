import uuid
from datetime import datetime
from pydantic import BaseModel
from app.models.backup_run import RunStatus, TriggerType
from app.models.backup_job import BackupType


class BackupJobCreate(BaseModel):
    name: str
    server_id: uuid.UUID
    backup_type: BackupType = BackupType.mssql
    db_instance_id: uuid.UUID | None = None
    folder_path: str | None = None
    storage_destination_id: uuid.UUID
    schedule_cron: str
    compression_enabled: bool = False
    mssql_native_compression: bool = True
    encryption_enabled: bool = False
    encryption_password: str | None = None
    retention_days: int = 30
    enabled: bool = True


class BackupJobUpdate(BaseModel):
    name: str | None = None
    db_instance_id: uuid.UUID | None = None
    folder_path: str | None = None
    storage_destination_id: uuid.UUID | None = None
    schedule_cron: str | None = None
    compression_enabled: bool | None = None
    mssql_native_compression: bool | None = None
    encryption_enabled: bool | None = None
    encryption_password: str | None = None
    retention_days: int | None = None
    enabled: bool | None = None


class BackupJobOut(BaseModel):
    id: uuid.UUID
    name: str
    server_id: uuid.UUID
    backup_type: BackupType
    db_instance_id: uuid.UUID | None
    folder_path: str | None
    storage_destination_id: uuid.UUID
    schedule_cron: str
    compression_enabled: bool
    mssql_native_compression: bool
    encryption_enabled: bool
    retention_days: int
    enabled: bool

    model_config = {"from_attributes": True}


class BackupRunOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    job_name: str | None = None
    started_at: datetime | None
    finished_at: datetime | None
    status: RunStatus
    size_bytes: int | None
    file_path: str | None
    error_message: str | None
    trigger_type: TriggerType

    # Piano 5.5b enrichment
    server_id: uuid.UUID | None = None
    server_name: str | None = None
    backup_type: str | None = None
    database_name: str | None = None
    folder_path: str | None = None
    storage_id: uuid.UUID | None = None
    storage_name: str | None = None
    storage_type: str | None = None
    retention_purged: bool = False
    encryption_enabled: bool = False
    velocity_mbps: float | None = None

    model_config = {"from_attributes": True}
