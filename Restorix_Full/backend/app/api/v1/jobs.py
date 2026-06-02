import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.backup_job import BackupJob
from app.models.backup_run import BackupRun, RunStatus, TriggerType
from app.models.server import Server
from app.models.user import User
from app.schemas.backup import BackupJobCreate, BackupJobUpdate, BackupJobOut, BackupRunOut
from app.api.deps import get_current_user
from app.core.encryption import encrypt
from croniter import croniter as _croniter


def _validate_cron(expr: str) -> None:
    if not _croniter.is_valid(expr):
        raise HTTPException(status_code=400, detail=f"Invalid cron expression: {expr!r}")
from app.services.audit import log_event, EventType
_logger = logging.getLogger(__name__)

router = APIRouter()


async def _safe_audit(db, **kwargs):
    """Best-effort audit log. Never raises — failures only warn."""
    try:
        await log_event(db, **kwargs)
        await db.commit()
    except Exception as audit_exc:
        _logger.warning("audit log failed: %s", audit_exc)


def _org_id(user: User) -> uuid.UUID:
    return user.org_id


@router.get("/", response_model=list[BackupJobOut])
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(BackupJob)
        .options(selectinload(BackupJob.db_instance))
        .where(BackupJob.org_id == _org_id(current_user))
        .order_by(BackupJob.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=BackupJobOut, status_code=201)
async def create_job(
    payload: BackupJobCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("superadmin", "admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    server = await db.get(Server, payload.server_id)
    if not server or server.org_id != _org_id(current_user):
        raise HTTPException(status_code=404, detail="Server not found")

    _validate_cron(payload.schedule_cron)  # Fix #8: validate before saving
    if payload.backup_type in ("mssql", "mysql") and not payload.db_instance_id:
        raise HTTPException(status_code=400, detail="db_instance_id required for database backup")
    if payload.backup_type == "folder" and not payload.folder_path:
        raise HTTPException(status_code=400, detail="folder_path required for folder backup")

    enc_password = None
    if payload.encryption_enabled and payload.encryption_password:
        enc_password = encrypt(payload.encryption_password)

    job = BackupJob(
        org_id=_org_id(current_user),
        server_id=payload.server_id,
        backup_type=payload.backup_type,
        db_instance_id=payload.db_instance_id if payload.backup_type in ("mssql", "mysql") else None,
        folder_path=payload.folder_path if payload.backup_type == "folder" else None,
        storage_destination_id=payload.storage_destination_id,
        name=payload.name,
        schedule_cron=payload.schedule_cron,
        compression_enabled=payload.compression_enabled,
        encryption_enabled=payload.encryption_enabled,
        encryption_password_enc=enc_password,
        retention_days=payload.retention_days,
        enabled=payload.enabled,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    bt = job.backup_type.value if hasattr(job.backup_type, "value") else str(job.backup_type)
    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.JOB_CREATED,
        target_type="backup_job", target_id=str(job.id),
        description=f"Created backup job {job.name} ({bt})",
        metadata={"name": job.name, "backup_type": bt, "server_id": str(job.server_id)},
        request=request,
    )

    return job


@router.get("/{job_id}", response_model=BackupJobOut)
async def get_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(BackupJob)
        .options(selectinload(BackupJob.db_instance))
        .where(BackupJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job or job.org_id != _org_id(current_user):
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.patch("/{job_id}", response_model=BackupJobOut)
async def update_job(
    job_id: uuid.UUID,
    payload: BackupJobUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("superadmin", "admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    job = await db.get(BackupJob, job_id)
    if not job or job.org_id != _org_id(current_user):
        raise HTTPException(status_code=404, detail="Job not found")

    if payload.name is not None:
        job.name = payload.name
    if payload.db_instance_id is not None:
        job.db_instance_id = payload.db_instance_id
    if payload.folder_path is not None:
        job.folder_path = payload.folder_path
    if payload.storage_destination_id is not None:
        job.storage_destination_id = payload.storage_destination_id
    if payload.schedule_cron is not None:
        _validate_cron(payload.schedule_cron)  # Fix #8: validate on update too
        job.schedule_cron = payload.schedule_cron
    if payload.compression_enabled is not None:
        job.compression_enabled = payload.compression_enabled
    if payload.retention_days is not None:
        job.retention_days = payload.retention_days
    if payload.enabled is not None:
        job.enabled = payload.enabled

    if payload.encryption_enabled is not None:
        job.encryption_enabled = payload.encryption_enabled
        if payload.encryption_password:
            job.encryption_password_enc = encrypt(payload.encryption_password)
        elif payload.encryption_enabled is False:
            job.encryption_password_enc = None

    db.add(job)
    await db.commit()
    await db.refresh(job)

    changed = [k for k, v in payload.model_dump(exclude_unset=True).items() if v is not None or k in ("encryption_enabled",)]
    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.JOB_UPDATED,
        target_type="backup_job", target_id=str(job.id),
        description=f"Updated backup job {job.name}",
        metadata={"name": job.name, "fields_changed": changed},
        request=request,
    )

    return job


@router.patch("/{job_id}/toggle", response_model=BackupJobOut)
async def toggle_job(
    job_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("superadmin", "admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    job = await db.get(BackupJob, job_id)
    if not job or job.org_id != _org_id(current_user):
        raise HTTPException(status_code=404, detail="Job not found")
    job.enabled = not job.enabled
    db.add(job)
    await db.commit()
    await db.refresh(job)

    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.JOB_UPDATED,
        target_type="backup_job", target_id=str(job.id),
        description=f"Toggled backup job {job.name} -> enabled={job.enabled}",
        metadata={"name": job.name, "fields_changed": ["enabled"], "enabled": bool(job.enabled)},
        request=request,
    )

    return job


@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    job = await db.get(BackupJob, job_id)
    if not job or job.org_id != _org_id(current_user):
        raise HTTPException(status_code=404, detail="Job not found")
    job_name = job.name
    job_id_str = str(job.id)
    await db.delete(job)
    await db.commit()

    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.JOB_DELETED,
        target_type="backup_job", target_id=job_id_str,
        description=f"Deleted backup job {job_name}",
        metadata={"name": job_name},
        request=request,
    )


@router.post("/{job_id}/run", response_model=BackupRunOut, status_code=201)
async def trigger_run(
    job_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a manual BackupRun (pending). The agent will pick it up."""
    if current_user.role not in ("superadmin", "admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    job = await db.get(BackupJob, job_id)
    if not job or job.org_id != _org_id(current_user):
        raise HTTPException(status_code=404, detail="Job not found")

    run = BackupRun(
        job_id=job_id,
        status=RunStatus.pending,
        trigger_type=TriggerType.manual,
        triggered_by_user_id=current_user.id,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.JOB_TRIGGERED_MANUAL,
        target_type="backup_job", target_id=str(job.id),
        description=f"Manually triggered backup job {job.name}",
        metadata={"name": job.name, "run_id": str(run.id)},
        request=request,
    )

    return run


@router.get("/{job_id}/runs", response_model=list[BackupRunOut])
async def list_runs(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = await db.get(BackupJob, job_id)
    if not job or job.org_id != _org_id(current_user):
        raise HTTPException(status_code=404, detail="Job not found")

    result = await db.execute(
        select(BackupRun)
        .options(
            selectinload(BackupRun.job).selectinload(BackupJob.server),
            selectinload(BackupRun.job).selectinload(BackupJob.db_instance),
            selectinload(BackupRun.job).selectinload(BackupJob.storage_destination),
        )
        .where(BackupRun.job_id == job_id)
        .order_by(BackupRun.created_at.desc())
        .limit(50)
    )
    from app.api.v1.runs import _serialize_run
    runs = result.scalars().all()
    return [_serialize_run(r) for r in runs]
