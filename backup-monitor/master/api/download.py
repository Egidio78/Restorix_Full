import subprocess, json, time
from fastapi import APIRouter, HTTPException, Cookie, Depends
from fastapi.responses import StreamingResponse, JSONResponse
import jwt
import db, config
from auth.sessions import get_session_user

router = APIRouter()

def _require_auth(session: str | None = Cookie(default=None)):
    if not session:
        raise HTTPException(status_code=401, detail="Non autenticato")
    user = get_session_user(session)
    if not user:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    return user

def _generate_download_token(vps_id: str, snapshot_id: str, folder: str | None) -> str:
    payload = {
        "vps_id": vps_id,
        "snapshot_id": snapshot_id,
        "folder": folder,
        "exp": int(time.time()) + 86400,  # 24h
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")

def _decode_download_token(token: str) -> dict:
    try:
        return jwt.decode(token, config.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=410, detail="Link scaduto")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Token non valido")

def _get_server_or_404(vps_id: str):
    with db.get_db() as conn:
        server = conn.execute("SELECT * FROM servers WHERE vps_id=?", (vps_id,)).fetchone()
    if not server:
        raise HTTPException(status_code=404, detail="VPS non trovata")
    return dict(server)

def _stream_restic(snapshot_id: str, path: str):
    cmd = ["restic", "dump", snapshot_id, path, "--archive", "tar"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        yield from proc.stdout
    finally:
        proc.stdout.close()
        proc.wait()

@router.get("/api/v1/servers/{vps_id}/snapshots/{snapshot_id}/download")
def download_snapshot(
    vps_id: str,
    snapshot_id: str,
    user=Depends(_require_auth),
):
    _get_server_or_404(vps_id)
    # Check size to decide: stream vs JWT link
    with db.get_db() as conn:
        run = conn.execute(
            "SELECT size_gb FROM backup_runs WHERE vps_id=? AND snapshot_id=?",
            (vps_id, snapshot_id)
        ).fetchone()
    size_gb = run["size_gb"] if run and run["size_gb"] else 0.0
    if size_gb > config.LARGE_FILE_THRESHOLD_GB:
        token = _generate_download_token(vps_id, snapshot_id, None)
        link = f"{config.MASTER_BASE_URL}/api/v1/download/token/{token}"
        return JSONResponse({"type": "large_file", "download_url": link, "expires_in_hours": 24})
    filename = f"{vps_id}-{snapshot_id}.tar.gz"
    return StreamingResponse(
        _stream_restic(snapshot_id, "/"),
        media_type="application/gzip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@router.get("/api/v1/servers/{vps_id}/snapshots/{snapshot_id}/download/{folder:path}")
def download_folder(
    vps_id: str,
    snapshot_id: str,
    folder: str,
    user=Depends(_require_auth),
):
    _get_server_or_404(vps_id)
    folder_path = f"/{folder}"
    filename = f"{vps_id}-{snapshot_id}-{folder.replace('/', '_')}.tar.gz"
    return StreamingResponse(
        _stream_restic(snapshot_id, folder_path),
        media_type="application/gzip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@router.get("/api/v1/download/token/{token}")
def download_by_token(token: str):
    payload = _decode_download_token(token)
    vps_id = payload["vps_id"]
    snapshot_id = payload["snapshot_id"]
    folder = payload.get("folder")
    _get_server_or_404(vps_id)
    path = f"/{folder}" if folder else "/"
    filename = f"{vps_id}-{snapshot_id}.tar.gz"
    return StreamingResponse(
        _stream_restic(snapshot_id, path),
        media_type="application/gzip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
