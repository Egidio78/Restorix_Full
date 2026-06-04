"""
Celery tasks for Restorix.
Main task: check_due_jobs - runs every minute via Celery Beat,
creates BackupRun records for jobs whose cron schedule is due.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from croniter import croniter
from app.celery_app import celery_app

logger = logging.getLogger(__name__)


def _scheduler_tz():
    """Timezone in which cron schedules are interpreted (user's wall-clock).
    Defaults to Europe/Rome; override with SCHEDULER_TIMEZONE env var."""
    from zoneinfo import ZoneInfo
    tz_name = os.environ.get("SCHEDULER_TIMEZONE", "Europe/Rome")
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("Europe/Rome")


def _is_due(cron_expr: str, now: datetime, window_seconds: int = 60) -> bool:
    """Return True if the cron expression fired within the last window_seconds."""
    try:
        cron = croniter(cron_expr, now - timedelta(seconds=window_seconds))
        next_fire = cron.get_next(datetime)
        return next_fire <= now
    except Exception:
        return False


@celery_app.task(name="tasks.check_due_jobs")
def check_due_jobs():
    """Check all enabled backup jobs and create BackupRun records for due ones."""
    asyncio.run(_check_due_jobs_async())


async def _check_due_jobs_async():
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import select
    from app.config import get_settings
    from app.models.backup_job import BackupJob
    from app.models.backup_run import BackupRun, RunStatus, TriggerType

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Evaluate cron schedules in the user's wall-clock timezone (Europe/Rome),
    # not UTC — otherwise a "02:00" cron fires at 04:00 Italian time.
    now = datetime.now(_scheduler_tz())

    async with SessionLocal() as db:
        try:
            result = await db.execute(
                select(BackupJob).where(BackupJob.enabled == True)
            )
            jobs = result.scalars().all()

            created_count = 0
            for job in jobs:
                if not _is_due(job.schedule_cron, now):
                    continue

                existing = await db.execute(
                    select(BackupRun).where(
                        BackupRun.job_id == job.id,
                        BackupRun.status.in_([RunStatus.pending, RunStatus.running]),
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                run = BackupRun(
                    job_id=job.id,
                    status=RunStatus.pending,
                    trigger_type=TriggerType.scheduler,
                )
                db.add(run)
                created_count += 1

            await db.commit()
            if created_count > 0:
                logger.info(f"check_due_jobs: created {created_count} new BackupRun records")

        except Exception as e:
            logger.error(f"check_due_jobs error: {e}")
            await db.rollback()

    await engine.dispose()


@celery_app.task(name="tasks.send_notifications")
def send_notifications(run_id: str):
    """Send email/webhook notifications for a completed backup run."""
    asyncio.run(_send_notifications_async(run_id))


async def _send_notifications_async(run_id: str):
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import select
    from app.config import get_settings
    from app.models.backup_run import BackupRun, RunStatus
    from app.models.backup_job import BackupJob
    from app.models.notification import NotificationChannel, ChannelType
    from app.core.encryption import decrypt
    import json

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as db:
        run = await db.get(BackupRun, run_id)
        if not run:
            return

        job = await db.get(BackupJob, run.job_id)
        if not job:
            return

        is_success = run.status == RunStatus.success

        result = await db.execute(
            select(NotificationChannel).where(
                NotificationChannel.org_id == job.org_id,
                NotificationChannel.enabled == True,
            )
        )
        channels = result.scalars().all()

        for channel in channels:
            if is_success and not channel.on_success:
                continue
            if not is_success and not channel.on_failure:
                continue

            try:
                config = json.loads(decrypt(channel.config_enc))
            except Exception:
                continue

            status_label = "Completato" if is_success else "Fallito"
            subject = f"[Restorix] Backup {status_label} - {job.name}"
            body_text = (
                f"Backup Job: {job.name}\n"
                f"Stato: {status_label}\n"
                f"Data: {run.finished_at}\n"
            )
            if run.size_bytes:
                body_text += f"Dimensione: {run.size_bytes / 1024 / 1024:.1f} MB\n"
            if run.error_message:
                body_text += f"Errore: {run.error_message}\n"

            if channel.channel_type == ChannelType.email:
                try:
                    _send_email(settings, config, subject, body_text)
                    logger.info(f"Email notification sent for run {run_id}")
                except Exception as e:
                    logger.error(f"Email notification failed: {e}")

            elif channel.channel_type == ChannelType.webhook:
                try:
                    _send_webhook(config, run, job, is_success)
                    logger.info(f"Webhook notification sent for run {run_id}")
                except Exception as e:
                    logger.error(f"Webhook notification failed: {e}")

    await engine.dispose()


def _send_email(settings, config: dict, subject: str, body: str):
    """Send email via SMTP."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    smtp_host = config.get("smtp_host") or settings.smtp_host
    smtp_port = int(config.get("smtp_port") or settings.smtp_port)
    smtp_user = config.get("smtp_user") or settings.smtp_user
    smtp_pass = config.get("smtp_password") or settings.smtp_password.get_secret_value()
    smtp_from = config.get("from") or settings.smtp_from
    to_addr = config.get("to", "")

    if not to_addr:
        raise ValueError("No 'to' address in email channel config")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = to_addr
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as s:
        s.ehlo()
        if smtp_port != 465:
            s.starttls()
        if smtp_user:
            s.login(smtp_user, smtp_pass)
        s.send_message(msg)


def _send_webhook(config: dict, run, job, is_success: bool):
    """Send webhook POST."""
    import requests as req
    import hmac
    import hashlib
    import json

    url = config.get("url", "")
    secret = config.get("secret", "")
    if not url:
        raise ValueError("No 'url' in webhook config")

    payload = {
        "event": "backup.success" if is_success else "backup.failed",
        "job_name": job.name,
        "run_id": str(run.id),
        "status": run.status,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "size_bytes": run.size_bytes,
        "error_message": run.error_message,
    }
    headers = {"Content-Type": "application/json", "User-Agent": "Restorix/1.0"}

    if secret:
        body_bytes = json.dumps(payload).encode()
        sig = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
        headers["X-Restorix-Signature"] = f"sha256={sig}"

    resp = req.post(url, json=payload, headers=headers, timeout=10)
    resp.raise_for_status()


# ============================================================
# Piano 5a — Retention cleanup tasks
# ============================================================


@celery_app.task(name="app.tasks.cleanup_scheduler")
def cleanup_scheduler():
    """Runs every 5 min. For each org, if cron fired in last 5 min, enqueue cleanup_org_runs."""
    from app.config import get_settings
    settings = get_settings()
    if not settings.RETENTION_ENABLED:
        return {"skipped": "RETENTION_ENABLED=false"}

    from app.database import AsyncSessionLocal
    from app.models.organization import Organization
    from sqlalchemy import select

    async def _scan():
        # Interpret cleanup cron in the user's wall-clock timezone (Europe/Rome)
        now = datetime.now(_scheduler_tz()).replace(tzinfo=None)
        window_start = now - timedelta(minutes=5)
        enqueued = []
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Organization))
            orgs = result.scalars().all()
            for org in orgs:
                try:
                    cron_expr = getattr(org, 'schedule_cleanup_cron', None) or '0 3 * * *'
                    prev_fire = croniter(cron_expr, now).get_prev(datetime)
                    if window_start <= prev_fire <= now:
                        cleanup_org_runs.delay(str(org.id))
                        enqueued.append(str(org.id))
                except Exception as e:
                    logger.warning("Invalid cron for org %s: %s", org.id, e)
        return {"enqueued": enqueued, "window": [window_start.isoformat(), now.isoformat()]}

    return asyncio.run(_scan())


@celery_app.task(name="app.tasks.forward_run_to_storage", bind=True, max_retries=0)
def forward_run_to_storage(self, shadow_run_id: str, source_run_id: str,
                           target_storage_id: str, mode: str, user_id: str | None):
    """Async storage-to-storage transfer (Piano 6e)."""
    from app.database import AsyncSessionLocal

    async def _run():
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from uuid import UUID
        from app.models.backup_run import BackupRun
        from app.models.backup_job import BackupJob
        from app.models.storage import StorageDestination
        from app.services.forward import ForwardService
        from app.services.audit import log_event, EventType

        async with AsyncSessionLocal() as db:
            src = (await db.execute(
                select(BackupRun)
                .options(
                    selectinload(BackupRun.job).selectinload(BackupJob.storage_destination),
                )
                .where(BackupRun.id == UUID(source_run_id))
            )).scalar_one()

            target = (await db.execute(
                select(StorageDestination).where(StorageDestination.id == UUID(target_storage_id))
            )).scalar_one()

            shadow = (await db.execute(
                select(BackupRun).where(BackupRun.id == UUID(shadow_run_id))
            )).scalar_one()

            try:
                svc = ForwardService(db)
                res = await svc.forward_run(src, target, mode, shadow)
                try:
                    await log_event(
                        db,
                        org_id=src.job.org_id,
                        user_id=UUID(user_id) if user_id else None,
                        event_type=EventType.RUN_FORWARDED,
                        target_type="backup_run",
                        target_id=str(src.id),
                        description=f"Forwarded run {src.id} → storage {target.name} (mode={mode})",
                        metadata={
                            "source_storage_id": str(src.job.storage_destination_id),
                            "source_storage_name": src.job.storage_destination.name,
                            "target_storage_id": str(target.id),
                            "target_storage_name": target.name,
                            "mode": mode,
                            "shadow_run_id": str(shadow.id),
                            "bytes": res["bytes"],
                            "duration_seconds": res["duration_seconds"],
                            "source_deleted": res["source_deleted"],
                        },
                    )
                    await db.commit()
                except Exception as audit_exc:
                    logging.getLogger(__name__).warning("audit log failed: %s", audit_exc)
                return res
            except Exception as e:
                # Shadow already marked failed by ForwardService
                return {"error": str(e), "shadow_run_id": shadow_run_id}

    return asyncio.run(_run())


@celery_app.task(name="app.tasks.cleanup_org_runs", bind=True, max_retries=0)
def cleanup_org_runs(self, org_id: str):
    """Run retention + audit purge for one org."""
    from app.database import AsyncSessionLocal
    from uuid import UUID

    async def _run():
        from app.services.retention import RetentionService
        async with AsyncSessionLocal() as db:
            service = RetentionService(db)
            report = await service.purge_org(UUID(org_id), dry_run=False)
            audit_deleted = await service.purge_audit(UUID(org_id))
            return {"purge": report.__dict__, "audit_deleted": audit_deleted}

    return asyncio.run(_run())
