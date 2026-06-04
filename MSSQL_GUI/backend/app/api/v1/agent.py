import uuid
import json
import re
import os
from datetime import datetime, timezone, timedelta

AGENT_VERSION_RE = re.compile(r'^[A-Za-z0-9.\-_]{1,50}$')
SEMVER_RE = re.compile(r'^\d+\.\d+\.\d+$')
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.server import Server, AgentStatus
from app.models.backup_job import BackupJob
from app.models.backup_run import BackupRun, RunStatus
from app.models.db_instance import DbInstance
from app.models.storage import StorageDestination
from app.core.encryption import decrypt
from app.core.agent_version import AGENT_VERSION
from app.services.instance_config import get_instance_config
from app.services.agent_install import render_install_script, render_install_script_windows
from app.services.audit import log_event, EventType
from app.schemas.agent_heartbeat import HeartbeatPayload, HeartbeatResponse

router = APIRouter()


AGENT_RELEASES_DIR = "/app/agent_releases"
UPDATE_IN_PROGRESS_TIMEOUT = timedelta(minutes=30)


def _release_tarball_path(version: str) -> str:
    return os.path.join(AGENT_RELEASES_DIR, f"dbshield-agent-{version}.tar.gz")


def _release_sha_path(version: str) -> str:
    return _release_tarball_path(version) + ".sha256"


def _read_sha256(version: str) -> str | None:
    path = _release_sha_path(version)
    try:
        with open(path, "r") as f:
            sha = f.read().strip().split()[0]
        if re.fullmatch(r"[0-9a-fA-F]{64}", sha):
            return sha.lower()
    except (FileNotFoundError, IndexError):
        return None
    return None


async def get_server_by_token(
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> Server:
    result = await db.execute(
        select(Server).where(Server.agent_token == token, Server.is_active == True)
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=401, detail="Invalid agent token")
    return server


class RunReport(BaseModel):
    status: str  # success | failed
    size_bytes: int | None = None
    file_path: str | None = None
    checksum_sha256: str | None = None
    error_message: str | None = None
    agent_version: str | None = None


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(
    payload: HeartbeatPayload | None = None,
    agent_version: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    server: Server = Depends(get_server_by_token),
):
    server.status = AgentStatus.online

    effective_version = (payload.agent_version if payload else None) or agent_version
    if effective_version and AGENT_VERSION_RE.match(effective_version):
        server.agent_version = effective_version

    if payload and payload.current_endpoint:
        server.last_heartbeat_endpoint = payload.current_endpoint.rstrip("/")

    # Auto-update timeout sweeper
    now = datetime.now(timezone.utc)
    if (
        server.last_update_status == "in_progress"
        and server.last_update_at is not None
        and (now - server.last_update_at) > UPDATE_IN_PROGRESS_TIMEOUT
    ):
        server.last_update_status = "failed"
        server.last_update_error = "Update timed out (no status report within 30min)"

    db.add(server)

    canonical = ""
    endpoint_version = ""
    try:
        config = await get_instance_config(db)
        canonical = (config.agent_endpoint or "").rstrip("/")
        endpoint_version = config.updated_at.isoformat() if config.updated_at else ""
    except Exception:
        pass

    if payload and payload.current_endpoint and canonical:
        if payload.current_endpoint.rstrip("/") == canonical:
            server.endpoint_version_seen = endpoint_version

    # Auto-update decision
    update_command: str | None = None
    download_url: str | None = None
    expected_sha256: str | None = None

    current_version = server.agent_version or ""

    # Anti-orphan: se admin ha cliccato "Aggiorna ora" ma l'agent e' gia' alla
    # versione corrente, resetta il flag (altrimenti rimarrebbe appeso e una
    # release futura lo consumerebbe inaspettatamente).
    if server.update_pending and current_version == AGENT_VERSION:
        server.update_pending = False

    should_update = (
        current_version != AGENT_VERSION
        and (server.auto_update or server.update_pending)
        and server.last_update_status != "in_progress"
    )
    if should_update:
        sha = _read_sha256(AGENT_VERSION)
        tarball_exists = os.path.isfile(_release_tarball_path(AGENT_VERSION))
        if sha and tarball_exists and canonical:
            update_command = f"update_to_{AGENT_VERSION}"
            download_url = f"{canonical}/api/v1/agent/download/{AGENT_VERSION}"
            expected_sha256 = sha

    await db.commit()

    return {
        "status": "ok",
        "server_id": str(server.id),
        "next_poll_seconds": 30,
        "canonical_endpoint": canonical,
        "endpoint_version": endpoint_version,
        "update_command": update_command,
        "download_url": download_url,
        "expected_sha256": expected_sha256,
    }


# Auto-update endpoints

@router.get("/check-update")
async def check_update(
    db: AsyncSession = Depends(get_db),
    server: Server = Depends(get_server_by_token),
):
    config = None
    try:
        config = await get_instance_config(db)
    except Exception:
        pass
    canonical = (config.agent_endpoint.rstrip("/") if config and config.agent_endpoint else "")

    current = server.agent_version or ""
    latest = AGENT_VERSION
    update_available = (
        current != latest
        and os.path.isfile(_release_tarball_path(latest))
    )
    sha = _read_sha256(latest) if update_available else None
    download_url = (
        f"{canonical}/api/v1/agent/download/{latest}"
        if (update_available and canonical) else None
    )

    return {
        "current_version": current,
        "latest_version": latest,
        "update_available": bool(update_available and sha and download_url),
        "download_url": download_url,
        "expected_sha256": sha,
        "force": bool(server.update_pending),
    }


@router.get("/download/{version}")
async def download_agent(version: str):
    if not SEMVER_RE.match(version):
        raise HTTPException(status_code=400, detail="Invalid version format")
    path = _release_tarball_path(version)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="Release not found")
    return FileResponse(
        path,
        media_type="application/gzip",
        filename=f"dbshield-agent-{version}.tar.gz",
    )


class UpdateStatusPayload(BaseModel):
    status: str
    from_version: str | None = None
    to_version: str | None = None
    error_message: str | None = None


VALID_UPDATE_STATUSES = {"in_progress", "success", "failed", "rolled_back"}


@router.post("/update-status")
async def report_update_status(
    payload: UpdateStatusPayload,
    db: AsyncSession = Depends(get_db),
    server: Server = Depends(get_server_by_token),
):
    if payload.status not in VALID_UPDATE_STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")

    server.last_update_at = datetime.now(timezone.utc)
    server.last_update_status = payload.status
    if payload.from_version and AGENT_VERSION_RE.match(payload.from_version):
        server.last_update_from_version = payload.from_version
    if payload.to_version and AGENT_VERSION_RE.match(payload.to_version):
        server.last_update_to_version = payload.to_version
    server.last_update_error = (payload.error_message or None)

    if payload.status == "success":
        if payload.to_version and AGENT_VERSION_RE.match(payload.to_version):
            server.agent_version = payload.to_version
        server.update_pending = False

    db.add(server)

    if payload.status == "success":
        event = EventType.AGENT_UPDATED
    elif payload.status in ("failed", "rolled_back"):
        event = EventType.AGENT_UPDATE_FAILED
    else:
        event = EventType.AGENT_UPDATED

    try:
        await log_event(
            db,
            org_id=server.org_id,
            user_id=None,
            event_type=event,
            target_type="server",
            target_id=str(server.id),
            description=f"Agent update {payload.status}: {payload.from_version or '?'} -> {payload.to_version or '?'}",
            metadata={
                "status": payload.status,
                "from_version": payload.from_version,
                "to_version": payload.to_version,
                "error_message": payload.error_message,
            },
        )
    except Exception:
        pass

    await db.commit()
    return {"status": "ok"}


@router.get("/jobs")
async def get_pending_jobs(
    db: AsyncSession = Depends(get_db),
    server: Server = Depends(get_server_by_token),
):
    server.status = AgentStatus.online
    db.add(server)

    result = await db.execute(
        select(BackupRun)
        .join(BackupJob, BackupRun.job_id == BackupJob.id)
        .where(
            BackupJob.server_id == server.id,
            BackupRun.status == RunStatus.pending,
        )
        .limit(5)
    )
    runs = result.scalars().all()

    if not runs:
        await db.commit()
        return []

    jobs_payload = []
    import logging as _logging
    _agent_logger = _logging.getLogger(__name__)
    for run in runs:
        try:
            job = await db.get(BackupJob, run.job_id)
            if not job:
                continue

            dbi = None
            if job.db_instance_id:
                dbi = await db.get(DbInstance, job.db_instance_id)
            storage = await db.get(StorageDestination, job.storage_destination_id)

            if not storage:
                continue
            backup_type_value = job.backup_type.value if hasattr(job.backup_type, "value") else str(job.backup_type)
            if backup_type_value == "mssql" and not dbi:
                continue

            db_creds = {}
            if dbi and dbi.credentials_enc:
                try:
                    db_creds = json.loads(decrypt(dbi.credentials_enc))
                except Exception:
                    pass

            storage_config = {}
            if storage.config_enc:
                try:
                    storage_config = json.loads(decrypt(storage.config_enc))
                except Exception:
                    pass

            enc_password = None
            if job.encryption_enabled and job.encryption_password_enc:
                try:
                    enc_password = decrypt(job.encryption_password_enc)
                except Exception:
                    pass

            run.status = RunStatus.running
            run.started_at = datetime.now(timezone.utc)
            db.add(run)
            await db.commit()

            jobs_payload.append({
                "run_id": str(run.id),
                "job_id": str(job.id),
                "job_name": job.name,
                "backup_type": backup_type_value,
                "folder_path": job.folder_path,
                "mssql_instance": dbi.mssql_instance if dbi else "",
                "db_name": dbi.name if dbi else "",
                "db_username": db_creds.get("username", "") if dbi else "",
                "db_password": db_creds.get("password", "") if dbi else "",
                "storage_type": storage.storage_type,
                "storage_config": storage_config,
                "compression_enabled": job.compression_enabled,
                "mssql_native_compression": job.mssql_native_compression,
                "encryption_enabled": job.encryption_enabled,
                "encryption_password": enc_password,
                "retention_days": job.retention_days,
            })
        except Exception as e:
            await db.rollback()
            _agent_logger.exception("Failed to mark run %s as running: %s", run.id, e)
            continue

    return jobs_payload


@router.post("/runs/{run_id}")
async def report_run(
    run_id: uuid.UUID,
    payload: RunReport,
    db: AsyncSession = Depends(get_db),
    server: Server = Depends(get_server_by_token),
):
    run = await db.get(BackupRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    job = await db.get(BackupJob, run.job_id)
    if not job or job.server_id != server.id:
        raise HTTPException(status_code=403, detail="Run does not belong to this server")

    run.status = RunStatus.success if payload.status == "success" else RunStatus.failed
    run.finished_at = datetime.now(timezone.utc)
    run.size_bytes = payload.size_bytes
    run.file_path = payload.file_path
    run.checksum_sha256 = payload.checksum_sha256
    run.error_message = payload.error_message

    if payload.agent_version and AGENT_VERSION_RE.match(payload.agent_version):
        server.agent_version = payload.agent_version

    db.add(run)
    db.add(server)
    await db.commit()

    from app.tasks import send_notifications
    send_notifications.delay(str(run_id))

    return {"status": "ok", "run_id": str(run_id)}


@router.get("/version")
async def agent_version():
    return {
        "version": AGENT_VERSION,
        "download_url": f"/api/v1/agent/download/{AGENT_VERSION}",
        "install_url": "/install.sh",
    }


@router.get("/migration-stats")
async def migration_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Statistiche migrazione agenti (Piano 7d sotto-pagina /settings/migration).

    Ritorna:
    - old_domain / new_domain / old_domain_expires_at (dal `instance_config`)
    - counts: total, migrated, pending, offline
    - agents: lista con server, endpoint corrente, ultimo heartbeat, stato
    """
    # superadmin or admin only
    role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Permessi insufficienti")

    config = None
    try:
        config = await get_instance_config(db)
    except Exception:
        pass

    new_domain = config.agent_endpoint.rstrip("/") if config and config.agent_endpoint else None
    old_domain = getattr(config, "old_domain", None) if config else None
    old_domain_expires_at = getattr(config, "old_domain_expires_at", None) if config else None

    # Carica tutti i server attivi della org corrente
    result = await db.execute(
        select(Server).where(
            Server.org_id == current_user.org_id,
            Server.is_active == True,
        )
    )
    servers = result.scalars().all()

    now = datetime.now(timezone.utc)
    offline_threshold = timedelta(minutes=5)

    agents = []
    total = len(servers)
    migrated = 0
    pending = 0
    offline = 0

    for s in servers:
        last_hb = getattr(s, "last_heartbeat_at", None)
        is_offline = last_hb is None or (now - last_hb) > offline_threshold
        endpoint = s.last_heartbeat_endpoint
        if is_offline:
            status_label = "offline"
            offline += 1
        elif endpoint and new_domain and endpoint.rstrip("/") == new_domain:
            status_label = "migrated"
            migrated += 1
        else:
            status_label = "pending"
            pending += 1

        agents.append({
            "id": str(s.id),
            "name": s.name,
            "hostname": s.hostname,
            "current_endpoint": endpoint,
            "last_heartbeat_at": last_hb.isoformat() if last_hb else None,
            "status": status_label,
        })

    return {
        "old_domain": old_domain,
        "new_domain": new_domain,
        "old_domain_expires_at": old_domain_expires_at.isoformat() if old_domain_expires_at else None,
        "total": total,
        "migrated": migrated,
        "pending": pending,
        "offline": offline,
        "agents": agents,
    }


@router.get("/install-script", response_class=PlainTextResponse)
async def get_install_script(db: AsyncSession = Depends(get_db)):
    config = await get_instance_config(db)
    if not config.setup_completed:
        raise HTTPException(status_code=503, detail="Setup not completed")

    restorix_url = (config.agent_endpoint or "").rstrip("/")
    if not restorix_url:
        raise HTTPException(status_code=503, detail="agent_endpoint not configured")

    rendered = render_install_script(restorix_url, AGENT_VERSION)
    return PlainTextResponse(content=rendered, media_type="text/x-shellscript")


@router.get("/install-script-windows", response_class=PlainTextResponse)
async def get_install_script_windows(db: AsyncSession = Depends(get_db)):
    """Render the PowerShell bootstrap installer for Windows agents.

    One-liner usage:
        $Env:AGENT_TOKEN = "..."; irm <url>/api/v1/agent/install-script-windows | iex
    """
    config = await get_instance_config(db)
    if not config.setup_completed:
        raise HTTPException(status_code=503, detail="Setup not completed")

    restorix_url = (config.agent_endpoint or "").rstrip("/")
    if not restorix_url:
        raise HTTPException(status_code=503, detail="agent_endpoint not configured")

    rendered = render_install_script_windows(restorix_url, AGENT_VERSION)
    return PlainTextResponse(content=rendered, media_type="text/plain; charset=utf-8")


# Discovery
from app.services import discovery as _discovery


class DiscoveryRequestOut(BaseModel):
    mssql_instance: str
    username: str
    password: str


class DiscoveryReportPayload(BaseModel):
    databases: list[str] = []
    error: str | None = None


@router.get("/discovery")
async def get_discovery_request(
    db: AsyncSession = Depends(get_db),
    server: Server = Depends(get_server_by_token),
):
    req = await _discovery.get_request_for_agent(server.id)
    if not req:
        return None
    return DiscoveryRequestOut(**req)


@router.post("/discovery/result")
async def report_discovery(
    payload: DiscoveryReportPayload,
    db: AsyncSession = Depends(get_db),
    server: Server = Depends(get_server_by_token),
):
    await _discovery.store_result(server.id, payload.databases, payload.error)
    await _discovery.consume_request(server.id)
    return {"status": "ok"}
