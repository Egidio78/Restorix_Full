from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
import db
from api.utils import verify_api_key

router = APIRouter()

class RestoreReport(BaseModel):
    vps_id: str
    status: str
    checksum_ok: int = 0
    duration_s: Optional[int] = None
    error_msg: Optional[str] = None

@router.post("/api/v1/restore/report", status_code=204)
def restore_report(report: RestoreReport, x_api_key: str = Header(...)):
    verify_api_key(report.vps_id, x_api_key)
    with db.get_db() as conn:
        server = conn.execute("SELECT vps_id FROM servers WHERE vps_id=?", (report.vps_id,)).fetchone()
        if not server:
            raise HTTPException(status_code=404, detail="VPS non registrata")

        last_run = conn.execute(
            "SELECT id FROM backup_runs WHERE vps_id=? ORDER BY id DESC LIMIT 1",
            (report.vps_id,)
        ).fetchone()
        backup_run_id = last_run["id"] if last_run else None
        conn.execute(
            """INSERT INTO restore_runs
               (vps_id, backup_run_id, status, checksum_ok, duration_s, error_msg)
               VALUES (?,?,?,?,?,?)""",
            (report.vps_id, backup_run_id, report.status, report.checksum_ok,
             report.duration_s, report.error_msg)
        )
