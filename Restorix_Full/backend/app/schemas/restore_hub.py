from datetime import datetime
from pydantic import BaseModel


class LastBackupInfo(BaseModel):
    file_name: str
    server_name: str | None
    storage_name: str | None
    finished_at: datetime


class NextBackupInfo(BaseModel):
    job_name: str
    server_name: str | None
    schedule_cron: str
    next_fire_at: datetime
    seconds_until: int


class RestoreHubSummary(BaseModel):
    total_backups: int
    success_count_30d: int
    fail_count_30d: int
    success_rate_30d: float
    total_size_bytes: int
    last_backup: LastBackupInfo | None = None
    next_backup: NextBackupInfo | None = None


class TempFolderInfo(BaseModel):
    name: str
    path: str
    size_bytes: int
    n_files: int
    created_at: datetime


class TempFolderListResponse(BaseModel):
    items: list[TempFolderInfo]
    total_size_bytes: int


class DeleteTempFolderResponse(BaseModel):
    ok: bool
    name: str
    size_bytes_freed: int
    message: str
