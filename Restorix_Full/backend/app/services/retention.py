"""RetentionService: purge old backup files from remote storage and old audit logs."""
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.encryption import decrypt
from app.models.audit import AuditLog
from app.models.backup_job import BackupJob
from app.models.backup_run import BackupRun
from app.models.organization import Organization
from app.services.audit import log_event, EventType
from app.services.uploaders import get_uploader

logger = logging.getLogger(__name__)

MAX_PURGE_ATTEMPTS = 5
MIN_AUDIT_RETENTION_DAYS = 90


def decrypt_storage_config(config_enc: str) -> dict:
    """Decrypt the JSON storage config stored as encrypted text."""
    plaintext = decrypt(config_enc)
    return json.loads(plaintext)


@dataclass
class PurgeResult:
    run_id: str
    success: bool
    error: str | None = None


@dataclass
class PurgeReport:
    org_id: str
    candidates: int
    purged: int
    failed: int
    abandoned: int
    dry_run: bool
    items: list[dict]  # [{run_id, remote_path, storage_type}]


class RetentionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def purge_run(self, run: BackupRun) -> PurgeResult:
        """Purge a single BackupRun's remote file. On success mark purged; on failure
        increment attempts and, after MAX_PURGE_ATTEMPTS, set purge_abandoned."""
        try:
            storage = run.job.storage_destination
            storage_type = storage.storage_type.value if hasattr(storage.storage_type, "value") else storage.storage_type
            config = decrypt_storage_config(storage.config_enc)
            uploader = get_uploader(storage_type, config)
            try:
                uploader.delete(run.file_path)
            except Exception as del_exc:  # noqa: BLE001
                # If the remote file no longer exists, the purge goal is already
                # achieved — treat "not found"/404 as success instead of retrying forever.
                msg = str(del_exc).lower()
                not_found = (
                    isinstance(del_exc, FileNotFoundError)
                    or "not found" in msg
                    or "404" in msg
                    or "no such file" in msg
                    or "nosuchkey" in msg
                    or "does not exist" in msg
                )
                if not not_found:
                    raise
                logger.info(
                    "Remote file %s already absent during purge of run %s; treating as success",
                    run.file_path, run.id,
                )
            run.retention_purged = True
            run.retention_purged_at = datetime.utcnow()
            run.retention_purge_error = None
            try:
                await log_event(
                    self.db,
                    org_id=run.job.org_id, user_id=None,
                    event_type=EventType.RETENTION_PURGED,
                    target_type="backup_run", target_id=str(run.id),
                    description=f"Purged {run.file_path} from {storage_type}",
                    metadata={"file_path": run.file_path, "storage_type": storage_type},
                )
            except Exception as audit_exc:
                logger.warning("audit log failed: %s", audit_exc)
            return PurgeResult(run_id=str(run.id), success=True)
        except Exception as e:  # noqa: BLE001 — intentionally broad
            run.retention_purge_attempts = (run.retention_purge_attempts or 0) + 1
            run.retention_purge_error = str(e)[:1000]
            abandoned_now = run.retention_purge_attempts >= MAX_PURGE_ATTEMPTS
            if abandoned_now:
                run.purge_abandoned = True
                logger.error(
                    "Purge abandoned for run %s after %s attempts: %s",
                    run.id, run.retention_purge_attempts, e,
                )
            try:
                await log_event(
                    self.db,
                    org_id=run.job.org_id, user_id=None,
                    event_type=EventType.RETENTION_PURGE_FAILED,
                    target_type="backup_run", target_id=str(run.id),
                    description=f"Failed to purge {run.file_path}: {str(e)[:200]}",
                    metadata={"error": str(e)[:1000], "attempts": run.retention_purge_attempts},
                )
            except Exception as audit_exc:
                logger.warning("audit log failed: %s", audit_exc)
            if abandoned_now:
                try:
                    await log_event(
                        self.db,
                        org_id=run.job.org_id, user_id=None,
                        event_type=EventType.RETENTION_PURGE_ABANDONED,
                        target_type="backup_run", target_id=str(run.id),
                        description=f"Purge abandoned after {MAX_PURGE_ATTEMPTS} attempts",
                        metadata={
                            "last_error": run.retention_purge_error or "",
                            "attempts": run.retention_purge_attempts,
                            "file_path": run.file_path,
                        },
                    )
                except Exception as audit_exc:
                    logger.warning("audit log failed: %s", audit_exc)
                # Admin notification (best-effort). send_notifications(run_id) is
                # the existing celery task; it relays per-run failure notifications
                # via the configured channels.
                try:
                    from app.tasks import send_notifications
                    send_notifications.delay(str(run.id))
                except Exception as notify_exc:
                    logger.critical(
                        "Purge abandoned for run %s but admin notification could not "
                        "be enqueued: %s. Manual intervention required for file %s.",
                        run.id, notify_exc, run.file_path,
                    )
            return PurgeResult(run_id=str(run.id), success=False, error=str(e))

    async def purge_org(self, org_id: UUID, dry_run: bool = False) -> PurgeReport:
        """Find and purge candidate BackupRuns for an organization."""
        result = await self.db.execute(
            select(BackupJob)
            .where(BackupJob.org_id == org_id)
            .options(selectinload(BackupJob.storage_destination))
        )
        jobs = result.scalars().all()

        candidates: list[BackupRun] = []
        for job in jobs:
            if not job.retention_days or job.retention_days < 1:
                continue
            cutoff = datetime.utcnow() - timedelta(days=job.retention_days)
            q = await self.db.execute(
                select(BackupRun).where(
                    BackupRun.job_id == job.id,
                    BackupRun.status == "success",
                    BackupRun.finished_at < cutoff,
                    BackupRun.retention_purged.is_(False),
                    BackupRun.purge_abandoned.is_(False),
                )
            )
            for run in q.scalars().all():
                # attach the already-loaded job so purge_run can access storage_destination
                run.job = job
                candidates.append(run)

        items = [
            {
                "run_id": str(r.id),
                "remote_path": r.file_path,
                "storage_type": (
                    r.job.storage_destination.storage_type.value
                    if hasattr(r.job.storage_destination.storage_type, "value")
                    else r.job.storage_destination.storage_type
                ),
            }
            for r in candidates
        ]

        if dry_run:
            return PurgeReport(
                org_id=str(org_id),
                candidates=len(candidates),
                purged=0,
                failed=0,
                abandoned=0,
                dry_run=True,
                items=items,
            )

        purged = failed = abandoned = 0
        for run in candidates:
            res = await self.purge_run(run)
            if res.success:
                purged += 1
            else:
                failed += 1
                if run.purge_abandoned:
                    abandoned += 1
            # Commit after each run so a crash never leaves a deleted file with
            # retention_purged still False (or loses attempt counters).
            await self.db.commit()

        return PurgeReport(
            org_id=str(org_id),
            candidates=len(candidates),
            purged=purged,
            failed=failed,
            abandoned=abandoned,
            dry_run=False,
            items=items,
        )

    async def purge_audit(self, org_id: UUID) -> int:
        """Delete audit logs older than max(org.audit_retention_days, 90). Returns rows deleted."""
        org = await self.db.get(Organization, org_id)
        if org is None:
            return 0
        days = max(org.audit_retention_days or 0, MIN_AUDIT_RETENTION_DAYS)
        cutoff = datetime.utcnow() - timedelta(days=days)
        stmt = sa_delete(AuditLog).where(
            AuditLog.org_id == org_id,
            AuditLog.created_at < cutoff,
        )
        result = await self.db.execute(stmt)
        rowcount = result.rowcount or 0
        try:
            await log_event(
                self.db,
                org_id=org_id, user_id=None,
                event_type=EventType.AUDIT_PURGED,
                description=f"Purged {rowcount} old audit log entries (retention {days} days)",
                metadata={"count": int(rowcount), "retention_days": int(days)},
            )
        except Exception as audit_exc:
            logger.warning("audit log failed: %s", audit_exc)
        await self.db.commit()
        return rowcount
