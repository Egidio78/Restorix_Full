import json
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
import db
from api.utils import verify_api_key

router = APIRouter()

class BackupReport(BaseModel):
    vps_id: str
    status: str          # 'ok' | 'failed'
    snapshot_id: Optional[str] = None
    size_gb: Optional[float] = None
    duration_s: Optional[int] = None
    downtime_s: Optional[int] = None
    error_msg: Optional[str] = None
    folders: Optional[list[str]] = None
    disk_free_pct: Optional[float] = None

@router.post("/api/v1/backup/report", status_code=204)
def backup_report(report: BackupReport, x_api_key: str = Header(...)):
    verify_api_key(report.vps_id, x_api_key)
    with db.get_db() as conn:
        server = conn.execute("SELECT vps_id FROM servers WHERE vps_id=?", (report.vps_id,)).fetchone()
        if not server:
            raise HTTPException(status_code=404, detail="VPS non registrata")
        conn.execute(
            """INSERT INTO backup_runs
               (vps_id, status, snapshot_id, size_gb, duration_s, downtime_s,
                error_msg, folders, disk_free_pct)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (report.vps_id, report.status, report.snapshot_id, report.size_gb,
             report.duration_s, report.downtime_s, report.error_msg,
             json.dumps(report.folders or []), report.disk_free_pct)
        )
