import uuid
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
import re
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from app.database import get_db
from app.models.server import Server, AgentStatus
from app.models.backup_job import BackupJob
from app.models.backup_run import BackupRun, RunStatus
from app.models.db_instance import DbInstance
from app.models.storage import StorageDestination
from app.core.encryption import decrypt

router = APIRouter()


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


_FILE_PATH_RE = re.compile(r'^[A-Za-z0-9/_\-\.]+$')


class RunReport(BaseModel):
    status: str  # "success" | "failed"
    size_bytes: int | None = None
    file_path: str | None = None
    checksum_sha256: str | None = None
    error_message: str | None = None
    agent_version: str | None = None


@router.post("/heartbeat")
async def heartbeat(
    agent_version: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    server: Server = Depends(get_server_by_token),
):
    """Agent calls this every 30s to signal its alive."""
    server.status = AgentStatus.online
    if agent_version:
        server.agent_version = agent_version
    db.add(server)
    await db.commit()
    return {"status": "ok", "server_id": str(server.id)}


@router.get("/jobs")
async def get_pending_jobs(
    db: AsyncSession = Depends(get_db),
    server: Server = Depends(get_server_by_token),
):
    """Returns pending BackupRun records for this server with full job config."""
    server.status = AgentStatus.online
    db.add(server)

    # Fix #2: SELECT FOR UPDATE SKIP LOCKED prevents two workers delivering same run
    # Fix #3: selectinload eliminates N+1 queries (1 query instead of up to 16)
    result = await db.execute(
        select(BackupRun)
        .join(BackupJob, BackupRun.job_id == BackupJob.id)
        .options(
            selectinload(BackupRun.job).selectinload(BackupJob.storage_destination),
            selectinload(BackupRun.job).selectinload(BackupJob.db_instance),
        )
        .where(
            BackupJob.server_id == server.id,
            BackupRun.status == RunStatus.pending,
        )
        .limit(5)
        .with_for_update(skip_locked=True)
    )
    runs = result.scalars().all()

    if not runs:
        await db.commit()
        return []

    jobs_payload = []
    for run in runs:
        job = run.job
        if not job:
            continue

        dbi = job.db_instance
        storage = job.storage_destination

        if not storage:
            run.status = RunStatus.failed
            run.error_message = "Storage destination not found or deleted"
            run.finished_at = datetime.now(timezone.utc)
            db.add(run)
            continue
        backup_type_value = job.backup_type.value if hasattr(job.backup_type, "value") else str(job.backup_type)
        if backup_type_value in ("mssql", "mysql") and not dbi:
            run.status = RunStatus.failed
            run.error_message = "Database instance not found or not linked"
            run.finished_at = datetime.now(timezone.utc)
            db.add(run)
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

        jobs_payload.append({
            "run_id": str(run.id),
            "job_id": str(job.id),
            "job_name": job.name,
            "server_name": server.name,
            "backup_type": backup_type_value,
            "folder_path": job.folder_path,
            "connection_string": dbi.connection_string if dbi else "",
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

    await db.commit()
    return jobs_payload


@router.post("/runs/{run_id}")
async def report_run(
    run_id: uuid.UUID,
    payload: RunReport,
    db: AsyncSession = Depends(get_db),
    server: Server = Depends(get_server_by_token),
):
    """Agent reports the result of a backup run."""
    run = await db.get(BackupRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    job = await db.get(BackupJob, run.job_id)
    if not job or job.server_id != server.id:
        raise HTTPException(status_code=403, detail="Run does not belong to this server")

    # Fix #5: only accept reports for runs that are actually running
    if run.status != RunStatus.running:
        raise HTTPException(status_code=409, detail=f"Run is in state '{run.status}', expected 'running'")

    # Fix #4: validate file_path to prevent path traversal
    if payload.file_path is not None:
        if not _FILE_PATH_RE.match(payload.file_path) or ".." in payload.file_path:
            raise HTTPException(status_code=400, detail="Invalid file_path")

    run.status = RunStatus.success if payload.status == "success" else RunStatus.failed
    run.finished_at = datetime.now(timezone.utc)
    run.size_bytes = payload.size_bytes
    run.file_path = payload.file_path
    run.checksum_sha256 = payload.checksum_sha256
    run.error_message = payload.error_message

    if payload.agent_version:
        server.agent_version = payload.agent_version

    db.add(run)
    db.add(server)
    await db.commit()

    from app.tasks import send_notifications
    send_notifications.delay(str(run_id))

    return {"status": "ok", "run_id": str(run_id)}


@router.get("/version")
async def agent_version():
    """Returns current agent version info."""
    return {
        "version": "1.0.0",
        "download_url": "/agent/dbshield-agent-1.0.0.tar.gz",
        "install_url": "/install.sh",
    }


# ── Discovery ─────────────────────────────────────────────
from app.services import discovery as _discovery


class DiscoveryRequestOut(BaseModel):
    connection_string: str
    username: str
    password: str
    engine: str = "mssql"


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
