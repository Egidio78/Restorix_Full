import hashlib
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
import db, config

router = APIRouter()

class RestoreReport(BaseModel):
    vps_id: str
    status: str
    checksum_ok: int = 0
    duration_s: Optional[int] = None
    error_msg: Optional[str] = None

def _verify_api_key(vps_id: str, api_key: str):
    expected = hashlib.sha256(f"{config.MASTER_SECRET}{vps_id}".encode()).hexdigest()
    if api_key != expected:
        raise HTTPException(status_code=401, detail="API key non valida")

@router.post("/api/v1/restore/report", status_code=204)
def restore_report(report: RestoreReport, x_api_key: str = Header(...)):
    _verify_api_key(report.vps_id, x_api_key)
    with db.get_db() as conn:
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
