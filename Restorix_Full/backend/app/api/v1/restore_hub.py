import logging
import os
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from croniter import croniter
from fastapi import APIRouter, Depends, HTTPException, Path as PathParam
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.api.deps import get_current_user
from app.models.backup_job import BackupJob
from app.models.backup_run import BackupRun
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.schemas.restore_hub import (
    RestoreHubSummary, LastBackupInfo, NextBackupInfo,
    TempFolderInfo, TempFolderListResponse, DeleteTempFolderResponse,
)
from app.services.audit import log_event, EventType

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/summary", response_model=RestoreHubSummary)
async def restore_hub_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = current_user.org_id

    # Total successful backups
    total_q = (
        select(func.count()).select_from(BackupRun)
        .join(BackupJob, BackupRun.job_id == BackupJob.id)
        .where(BackupJob.org_id == org_id, BackupRun.status == "success")
    )
    total = (await db.execute(total_q)).scalar_one()

    # Total size
    size_q = (
        select(func.coalesce(func.sum(BackupRun.size_bytes), 0)).select_from(BackupRun)
        .join(BackupJob, BackupRun.job_id == BackupJob.id)
        .where(BackupJob.org_id == org_id, BackupRun.status == "success")
    )
    total_size = (await db.execute(size_q)).scalar_one()

    # Success / fail count last 30 days
    cutoff_30d = datetime.utcnow() - timedelta(days=30)
    succ_q = (
        select(func.count()).select_from(BackupRun)
        .join(BackupJob, BackupRun.job_id == BackupJob.id)
        .where(BackupJob.org_id == org_id, BackupRun.status == "success", BackupRun.started_at >= cutoff_30d)
    )
    fail_q = (
        select(func.count()).select_from(BackupRun)
        .join(BackupJob, BackupRun.job_id == BackupJob.id)
        .where(BackupJob.org_id == org_id, BackupRun.status == "failed", BackupRun.started_at >= cutoff_30d)
    )
    success_30 = (await db.execute(succ_q)).scalar_one()
    fail_30 = (await db.execute(fail_q)).scalar_one()
    total_30 = success_30 + fail_30
    rate = round((success_30 / total_30) * 100, 1) if total_30 > 0 else 0.0

    # Last backup
    last_q = (
        select(BackupRun)
        .options(
            selectinload(BackupRun.job).selectinload(BackupJob.server),
            selectinload(BackupRun.job).selectinload(BackupJob.storage_destination),
        )
        .join(BackupJob, BackupRun.job_id == BackupJob.id)
        .where(BackupJob.org_id == org_id, BackupRun.status == "success", BackupRun.finished_at.isnot(None))
        .order_by(BackupRun.finished_at.desc())
        .limit(1)
    )
    last_run = (await db.execute(last_q)).scalar_one_or_none()
    last_info = None
    if last_run:
        last_info = LastBackupInfo(
            file_name=Path(last_run.file_path or "").name or "?",
            server_name=last_run.job.server.name if last_run.job and last_run.job.server else None,
            storage_name=last_run.job.storage_destination.name if last_run.job and last_run.job.storage_destination else None,
            finished_at=last_run.finished_at,
        )

    # Next backup — soonest job
    jobs_q = (
        select(BackupJob).options(selectinload(BackupJob.server))
        .where(BackupJob.org_id == org_id, BackupJob.enabled == True)
    )
    jobs = (await db.execute(jobs_q)).scalars().all()
    now = datetime.utcnow()
    soonest_dt = None
    soonest_job = None
    for job in jobs:
        try:
            nxt = croniter(job.schedule_cron, now).get_next(datetime)
            if soonest_dt is None or nxt < soonest_dt:
                soonest_dt = nxt
                soonest_job = job
        except Exception as e:
            logger.warning("Invalid cron %r for job %s: %s", job.schedule_cron, job.id, e)

    next_info = None
    if soonest_job and soonest_dt:
        seconds_until = max(0, int((soonest_dt - now).total_seconds()))
        next_info = NextBackupInfo(
            job_name=soonest_job.name,
            server_name=soonest_job.server.name if soonest_job.server else None,
            schedule_cron=soonest_job.schedule_cron,
            next_fire_at=soonest_dt,
            seconds_until=seconds_until,
        )

    return RestoreHubSummary(
        total_backups=total,
        success_count_30d=success_30,
        fail_count_30d=fail_30,
        success_rate_30d=rate,
        total_size_bytes=int(total_size or 0),
        last_backup=last_info,
        next_backup=next_info,
    )


TEMP_FOLDER_NAME_RE = re.compile(r"^restore_[A-Za-z0-9_\-]+$")


def _validate_temp_folder_name(name: str) -> None:
    if not TEMP_FOLDER_NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="Nome cartella non valido")


def _resolve_under(parent: Path, name: str) -> Path:
    """Resolve name under parent, ensuring no path escape."""
    target = (parent / name).resolve()
    parent_resolved = parent.resolve()
    try:
        target.relative_to(parent_resolved)
    except ValueError:
        raise HTTPException(status_code=400, detail="Path traversal rifiutato")
    return target


def _folder_stats(p: Path) -> tuple[int, int, datetime]:
    """Return (size_bytes, n_files, created_at)."""
    total_size = 0
    n_files = 0
    for root, dirs, files in os.walk(p):
        for f in files:
            try:
                fp = Path(root) / f
                st = fp.stat()
                total_size += st.st_size
                n_files += 1
            except Exception:
                continue
    try:
        created = datetime.fromtimestamp(p.stat().st_mtime)
    except Exception:
        created = datetime.utcnow()
    return total_size, n_files, created


@router.get("/temp-folders", response_model=TempFolderListResponse)
async def list_temp_folders(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org = await db.get(Organization, current_user.org_id)
    if not org or not org.restore_temp_dir:
        return TempFolderListResponse(items=[], total_size_bytes=0)

    base = Path(org.restore_temp_dir)
    if not base.exists() or not base.is_dir():
        return TempFolderListResponse(items=[], total_size_bytes=0)

    items: list[TempFolderInfo] = []
    grand_total = 0
    for entry in sorted(base.iterdir()):
        try:
            if not entry.is_dir():
                continue
            if not TEMP_FOLDER_NAME_RE.match(entry.name):
                continue
            size, nf, created = _folder_stats(entry)
            grand_total += size
            items.append(TempFolderInfo(
                name=entry.name,
                path=str(entry),
                size_bytes=size,
                n_files=nf,
                created_at=created,
            ))
        except Exception as e:
            logger.warning("Skipping temp folder %s: %s", entry, e)
    return TempFolderListResponse(items=items, total_size_bytes=grand_total)


@router.delete("/temp-folders/{name}", response_model=DeleteTempFolderResponse)
async def delete_temp_folder(
    name: str = PathParam(..., max_length=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role_val not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Forbidden")

    _validate_temp_folder_name(name)

    org = await db.get(Organization, current_user.org_id)
    if not org or not org.restore_temp_dir:
        raise HTTPException(status_code=404, detail="restore_temp_dir non configurato")

    base = Path(org.restore_temp_dir)
    target = _resolve_under(base, name)
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail=f"Cartella '{name}' non esistente")

    size_before, _, _ = _folder_stats(target)
    shutil.rmtree(target)

    try:
        await log_event(
            db,
            org_id=org.id,
            user_id=current_user.id,
            event_type=EventType.RESTORE_TEMP_FOLDER_DELETED,
            target_type="restore_temp_folder",
            target_id=None,
            description=f"Deleted restore temp folder {name}",
            metadata={"name": name, "size_bytes_freed": size_before},
        )
        await db.commit()
    except Exception as e:
        logger.warning("audit log failed: %s", e)

    return DeleteTempFolderResponse(
        ok=True,
        name=name,
        size_bytes_freed=size_before,
        message=f"Cartella {name} cancellata, liberati {size_before} bytes",
    )
