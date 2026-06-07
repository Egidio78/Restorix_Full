import hashlib, json
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
import db, config
from api.utils import verify_api_key

router = APIRouter()

class RegisterServer(BaseModel):
    vps_id: str
    hostname: str
    cliente: str = ""
    os_name: str = ""
    os_version: str = ""
    folders: list[str] = []
    backup_hour: int = 2

@router.post("/api/v1/servers/register", status_code=201)
def register_server(payload: RegisterServer, x_api_key: str = Header(...)):
    # Registration uses a global key derived from MASTER_SECRET
    expected = hashlib.sha256(f"{config.MASTER_SECRET}register".encode()).hexdigest()
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Non autorizzato")
    vps_api_key = hashlib.sha256(f"{config.MASTER_SECRET}{payload.vps_id}".encode()).hexdigest()
    with db.get_db() as conn:
        conn.execute(
            """INSERT INTO servers (vps_id,hostname,cliente,os_name,os_version,folders,backup_hour,api_key)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(vps_id) DO UPDATE SET
               hostname=excluded.hostname, cliente=excluded.cliente,
               os_name=excluded.os_name, os_version=excluded.os_version,
               folders=excluded.folders, backup_hour=excluded.backup_hour""",
            (payload.vps_id, payload.hostname, payload.cliente,
             payload.os_name, payload.os_version,
             json.dumps(payload.folders), payload.backup_hour, vps_api_key)
        )
    return {"api_key": vps_api_key}

@router.get("/api/v1/servers")
def list_servers():
    with db.get_db() as conn:
        rows = conn.execute("""
            SELECT s.*,
                   br.status AS last_backup_status,
                   br.reported_at AS last_backup_at,
                   br.size_gb, br.duration_s, br.downtime_s,
                   br.snapshot_id, br.disk_free_pct,
                   rr.status AS last_restore_status
            FROM servers s
            LEFT JOIN backup_runs br ON br.id = (
                SELECT id FROM backup_runs WHERE vps_id=s.vps_id ORDER BY id DESC LIMIT 1)
            LEFT JOIN restore_runs rr ON rr.id = (
                SELECT id FROM restore_runs WHERE vps_id=s.vps_id ORDER BY id DESC LIMIT 1)
            ORDER BY s.vps_id
        """).fetchall()
    return [dict(r) for r in rows]

@router.get("/api/v1/servers/{vps_id}")
def server_detail(vps_id: str):
    with db.get_db() as conn:
        server = conn.execute("SELECT * FROM servers WHERE vps_id=?", (vps_id,)).fetchone()
        if not server:
            raise HTTPException(status_code=404, detail="VPS non trovata")
        runs = conn.execute(
            """SELECT br.*, rr.status AS restore_status, rr.checksum_ok
               FROM backup_runs br
               LEFT JOIN restore_runs rr ON rr.backup_run_id = br.id
               WHERE br.vps_id=? ORDER BY br.id DESC LIMIT 14""",
            (vps_id,)
        ).fetchall()
    return {"server": dict(server), "runs": [dict(r) for r in runs]}

@router.get("/api/v1/servers/{vps_id}/latest-snapshot")
def latest_snapshot(vps_id: str, x_api_key: str = Header(...)):
    verify_api_key(vps_id, x_api_key)
    with db.get_db() as conn:
        run = conn.execute(
            "SELECT snapshot_id FROM backup_runs WHERE vps_id=? AND status='ok' ORDER BY id DESC LIMIT 1",
            (vps_id,)
        ).fetchone()
    if not run:
        raise HTTPException(status_code=404, detail="Nessun snapshot disponibile")
    return {"snapshot_id": run["snapshot_id"]}
