import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.models.backup_run import BackupRun, RunStatus, TriggerType
from app.models.backup_job import BackupJob
from app.models.storage import StorageDestination
from app.models.user import User, UserRole
from app.schemas.backup import BackupRunOut
from app.schemas.forward import ForwardRequest, ForwardResponse
from app.api.deps import get_current_user
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


def _serialize_run(r: BackupRun) -> BackupRunOut:
    job = r.job
    db_inst = job.db_instance if job else None
    storage = job.storage_destination if job else None
    server = job.server if job else None
    bt = None
    if job and job.backup_type is not None:
        bt = job.backup_type.value if hasattr(job.backup_type, "value") else job.backup_type
    st = None
    if storage and storage.storage_type is not None:
        st = storage.storage_type.value if hasattr(storage.storage_type, "value") else storage.storage_type
    velocity_mbps = None
    if r.size_bytes and r.started_at and r.finished_at:
        duration = (r.finished_at - r.started_at).total_seconds()
        if duration > 0:
            velocity_mbps = round((r.size_bytes / duration) / (1024 * 1024), 2)
    return BackupRunOut(
        id=r.id,
        job_id=r.job_id,
        job_name=job.name if job else None,
        started_at=r.started_at,
        finished_at=r.finished_at,
        status=r.status,
        size_bytes=r.size_bytes,
        file_path=r.file_path,
        error_message=r.error_message,
        trigger_type=r.trigger_type,
        server_id=job.server_id if job else None,
        server_name=server.name if server else None,
        backup_type=bt,
        database_name=db_inst.name if db_inst else None,
        folder_path=job.folder_path if job else None,
        storage_id=job.storage_destination_id if job else None,
        storage_name=storage.name if storage else None,
        storage_type=st,
        retention_purged=bool(r.retention_purged),
        encryption_enabled=bool(job.encryption_enabled) if job else False,
        velocity_mbps=velocity_mbps,
    )


@router.get("/", response_model=list[BackupRunOut])
async def list_all_runs(
    limit: int = 50,
    status: RunStatus | None = None,
    server_id: uuid.UUID | None = None,
    storage_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List recent backup runs for the current organization, with optional filters."""
    stmt = (
        select(BackupRun)
        .join(BackupJob, BackupRun.job_id == BackupJob.id)
        .options(
            selectinload(BackupRun.job).selectinload(BackupJob.server),
            selectinload(BackupRun.job).selectinload(BackupJob.db_instance),
            selectinload(BackupRun.job).selectinload(BackupJob.storage_destination),
        )
        .where(BackupJob.org_id == current_user.org_id)
        .order_by(BackupRun.created_at.desc())
        .limit(min(limit, 200))
    )
    if status is not None:
        stmt = stmt.where(BackupRun.status == status)
    if server_id is not None:
        stmt = stmt.where(BackupJob.server_id == server_id)
    if storage_id is not None:
        stmt = stmt.where(BackupJob.storage_destination_id == storage_id)

    result = await db.execute(stmt)
    runs = result.scalars().all()
    return [_serialize_run(r) for r in runs]


@router.delete("/{run_id}", status_code=204)
async def delete_run(
    run_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.superadmin:
        raise HTTPException(status_code=403, detail="Only SuperAdmin can delete logs")
    run = await db.get(BackupRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    job = await db.get(BackupJob, run.job_id)
    if not job or job.org_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Run not found")
    run_id_str = str(run.id)
    await db.delete(run)
    await db.commit()

    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.RUN_DELETED,
        target_type="backup_run", target_id=run_id_str,
        description=f"Deleted backup run {run_id_str}",
        metadata={"job_id": str(job.id), "job_name": job.name},
        request=request,
    )


@router.delete("/", status_code=204)
async def delete_all_runs(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete ALL backup runs for the current organization. SuperAdmin only."""
    if current_user.role != UserRole.superadmin:
        raise HTTPException(status_code=403, detail="Only SuperAdmin can delete logs")
    jobs_result = await db.execute(select(BackupJob.id).where(BackupJob.org_id == current_user.org_id))
    job_ids = [r[0] for r in jobs_result.all()]
    deleted_count = 0
    if job_ids:
        # Count first so we can record it in the audit log
        count_q = await db.execute(
            select(BackupRun).where(BackupRun.job_id.in_(job_ids))
        )
        deleted_count = len(count_q.scalars().all())
        await db.execute(delete(BackupRun).where(BackupRun.job_id.in_(job_ids)))
        await db.commit()

    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.RUN_DELETED_BULK,
        description=f"Bulk deleted {deleted_count} backup runs",
        metadata={"count": int(deleted_count)},
        request=request,
    )


from fastapi import BackgroundTasks, Query
from pydantic import BaseModel
from app.services.restore import RestoreService
from app.core.rate_limit import limiter


class SendToTempResponse(BaseModel):
    status: str = "ok"
    target_path: str
    folder_path: str
    bytes: int
    decrypted: bool
    duration_seconds: float


@router.get('/{run_id}/download')
@limiter.limit('5/minute')
async def download_run(
    request: Request,
    run_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    decrypt: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Role check
    if current_user.role not in (UserRole.superadmin, UserRole.admin, UserRole.operator):
        raise HTTPException(status_code=403, detail='Forbidden')

    # Load run with relations
    result = await db.execute(
        select(BackupRun)
        .options(
            selectinload(BackupRun.job).selectinload(BackupJob.storage_destination),
        )
        .where(BackupRun.id == run_id)
    )
    run = result.scalar_one_or_none()

    if run is None:
        raise HTTPException(status_code=404, detail='Run not found')

    # Multi-tenancy
    if run.job.org_id != current_user.org_id and current_user.role != UserRole.superadmin:
        raise HTTPException(status_code=403, detail='Forbidden')

    if run.status != RunStatus.success:
        raise HTTPException(status_code=400, detail='Run is not successful, nothing to download')

    if run.retention_purged:
        raise HTTPException(status_code=410, detail='Backup has been purged by retention policy')

    # Audit: restore requested
    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.RESTORE_REQUESTED,
        target_type='backup_run', target_id=str(run_id),
        description=f'Restore requested for run {run_id}',
        metadata={'decrypt': decrypt},
        request=request,
    )

    service = RestoreService(db)
    try:
        response = await service.generate_response(run, decrypt=decrypt, background_tasks=background_tasks)
    except Exception as _exc:
        _logger.error("generate_response failed: %s", _exc, exc_info=True)
        raise

    # Audit: download served
    st = run.job.storage_destination.storage_type
    st_str = st.value if hasattr(st, 'value') else str(st)
    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.RESTORE_DOWNLOADED,
        target_type='backup_run', target_id=str(run_id),
        description=f'Download served for run {run_id}',
        metadata={'decrypt': decrypt, 'storage_type': st_str},
        request=request,
    )

    return response


@router.post('/{run_id}/send-to-temp', response_model=SendToTempResponse)
async def send_run_to_temp(
    request: Request,
    run_id: uuid.UUID,
    decrypt: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download a successful backup run and place it under the org's restore-temp dir.

    Returns the absolute folder/file paths so the operator can restore manually.
    """
    role_val = current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
    if role_val not in ('superadmin', 'admin', 'operator'):
        raise HTTPException(status_code=403, detail='Forbidden')

    result = await db.execute(
        select(BackupRun)
        .options(
            selectinload(BackupRun.job).selectinload(BackupJob.storage_destination),
        )
        .where(BackupRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail='Run not found')

    if run.job.org_id != current_user.org_id and role_val != 'superadmin':
        raise HTTPException(status_code=403, detail='Forbidden')

    if run.status != RunStatus.success:
        raise HTTPException(status_code=400, detail='Run is not successful')

    if run.retention_purged:
        raise HTTPException(status_code=410, detail='Backup has been purged by retention policy')

    service = RestoreService(db)
    res = await service.send_to_temp(run, decrypt=decrypt)

    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.RESTORE_SENT_TO_TEMP,
        target_type='backup_run', target_id=str(run_id),
        description=f'Sent run {run_id} to {res.folder_path}',
        metadata={
            'target_path': res.target_path,
            'folder_path': res.folder_path,
            'bytes': res.bytes,
            'decrypted': res.decrypted,
            'duration_seconds': res.duration_seconds,
        },
        request=request,
    )

    return SendToTempResponse(
        status='ok',
        target_path=res.target_path,
        folder_path=res.folder_path,
        bytes=res.bytes,
        decrypted=res.decrypted,
        duration_seconds=res.duration_seconds,
    )


@router.post("/{run_id}/forward", response_model=ForwardResponse, status_code=202)
async def forward_run(
    request: Request,
    run_id: uuid.UUID,
    payload: ForwardRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enqueue an async storage-to-storage forward of a successful backup run (Piano 6e)."""
    role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role_val not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden — solo superadmin/admin possono spostare backup")

    # Load source run with relations
    result = await db.execute(
        select(BackupRun)
        .options(selectinload(BackupRun.job).selectinload(BackupJob.storage_destination))
        .where(BackupRun.id == run_id)
    )
    source = result.scalar_one_or_none()
    if source is None:
        raise HTTPException(status_code=404, detail="Run not found")
    if source.job.org_id != current_user.org_id and role_val != "superadmin":
        raise HTTPException(status_code=403, detail="Forbidden")
    if str(source.status).lower() not in ("success", "runstatus.success"):
        raise HTTPException(status_code=400, detail="Run is not successful")
    if source.retention_purged:
        raise HTTPException(status_code=410, detail="Backup has been purged")
    if source.job.storage_destination_id == payload.target_storage_id:
        raise HTTPException(status_code=400, detail="Target storage must differ from source")

    # Validate target storage
    target = (await db.execute(
        select(StorageDestination).where(StorageDestination.id == payload.target_storage_id)
    )).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="Target storage not found")
    if target.org_id != source.job.org_id:
        raise HTTPException(status_code=403, detail="Target storage belongs to a different organization")

    # Create shadow run
    from datetime import datetime
    shadow = BackupRun(
        id=uuid.uuid4(),
        job_id=source.job_id,
        status=RunStatus.pending if hasattr(RunStatus, "pending") else "pending",
        started_at=datetime.utcnow(),
        trigger_type=TriggerType.forwarded,
        parent_run_id=source.id,
    )
    db.add(shadow)
    await db.commit()
    await db.refresh(shadow)

    # Enqueue Celery task
    from app.tasks import forward_run_to_storage
    async_result = forward_run_to_storage.delay(
        str(shadow.id),
        str(source.id),
        str(target.id),
        payload.mode,
        str(current_user.id),
    )

    return ForwardResponse(
        status="accepted",
        task_id=async_result.id,
        shadow_run_id=shadow.id,
    )
