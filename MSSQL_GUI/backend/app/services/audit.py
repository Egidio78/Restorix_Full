"""Audit logging service.

Centralized helper to write AuditLog rows from any route/service.
Caller is responsible for db.commit() (we only db.add()+flush()).
"""
from __future__ import annotations

import json
from enum import Enum
from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


class EventType(str, Enum):
    # Auth (7)
    AUTH_LOGIN_SUCCESS = "auth.login.success"
    AUTH_LOGIN_FAILED = "auth.login.failed"
    AUTH_LOGOUT = "auth.logout"
    AUTH_PASSWORD_CHANGED = "auth.password.changed"
    AUTH_2FA_ENABLED = "auth.2fa.enabled"
    AUTH_2FA_DISABLED = "auth.2fa.disabled"
    AUTH_2FA_BACKUP_CODES_REGENERATED = "auth.2fa.backup_codes.regenerated"

    # User (4)
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DEACTIVATED = "user.deactivated"
    USER_ROLE_CHANGED = "user.role.changed"

    # Server (4)
    SERVER_CREATED = "server.created"
    SERVER_UPDATED = "server.updated"
    SERVER_DELETED = "server.deleted"
    SERVER_AGENT_TOKEN_REGENERATED = "server.agent.token.regenerated"

    # DbInstance (3)
    DBINSTANCE_CREATED = "dbinstance.created"
    DBINSTANCE_UPDATED = "dbinstance.updated"
    DBINSTANCE_DELETED = "dbinstance.deleted"

    # Storage (4)
    STORAGE_CREATED = "storage.created"
    STORAGE_UPDATED = "storage.updated"
    STORAGE_DELETED = "storage.deleted"
    STORAGE_TESTED = "storage.tested"

    # Job (4)
    JOB_CREATED = "job.created"
    JOB_UPDATED = "job.updated"
    JOB_DELETED = "job.deleted"
    JOB_TRIGGERED_MANUAL = "job.triggered.manual"

    # Run (2)
    RUN_DELETED = "run.deleted"
    RUN_DELETED_BULK = "run.deleted.bulk"

    # Restore (4)
    RESTORE_REQUESTED = "restore.requested"
    RESTORE_DOWNLOADED = "restore.downloaded"
    RESTORE_FAILED_DISK_FULL = "restore.failed.disk_full"
    RESTORE_FAILED_UNAUTHORIZED = "restore.failed.unauthorized"

    # Retention / system (user_id=None) (4)
    RETENTION_PURGED = "retention.purged"
    RETENTION_PURGE_FAILED = "retention.purge.failed"
    RETENTION_PURGE_ABANDONED = "retention.purge.abandoned"
    AUDIT_PURGED = "audit.purged"

    # Org settings (2)
    ORG_SETTINGS_UPDATED = "org.settings.updated"
    ORG_SETTINGS_TEMPDIR_VERIFIED = "org.settings.tempdir.verified"

    # Restore temp folders (1)
    RESTORE_TEMP_FOLDER_DELETED = "restore.temp_folder.deleted"

    # Restore send-to-temp (Piano 6d)
    RESTORE_SENT_TO_TEMP = "restore.sent_to_temp"

    # Forward run to another storage (Piano 6e)
    RUN_FORWARDED = "run.forwarded"

    # License (Piano 7a) (8)
    LICENSE_UPLOADED = "license.uploaded"
    LICENSE_DEMO_STARTED = "license.demo_started"
    LICENSE_EXPIRED = "license.expired"
    LICENSE_GRACE_ENDED_READONLY = "license.grace_ended_readonly"
    LICENSE_LOCKED = "license.locked"
    LICENSE_LIMIT_REACHED_SERVER = "license.limit_reached.server"
    LICENSE_LIMIT_REACHED_DATABASE = "license.limit_reached.database"
    LICENSE_LIMIT_REACHED_FOLDER = "license.limit_reached.folder"
    LICENSE_DELETED = "license.deleted"

    # Instance / white-label (Piano 7c) (8)
    INSTANCE_SETUP_COMPLETED        = "instance.setup_completed"
    INSTANCE_DOMAIN_CHANGED         = "instance.domain.changed"
    INSTANCE_EMAIL_FROM_CHANGED     = "instance.email_from.changed"
    INSTANCE_SSL_RENEWED            = "instance.ssl.renewed"
    INSTANCE_SSL_RENEWAL_FAILED     = "instance.ssl.renewal_failed"
    INSTANCE_SSL_UPLOADED           = "instance.ssl.uploaded"
    INSTANCE_OLD_DOMAIN_EXPIRED     = "instance.old_domain.expired"
    AGENT_ENDPOINT_MIGRATED         = "agent.endpoint.migrated"

    # Agent auto-update (Piano 8 / migration 0014)
    AGENT_UPDATED                   = "agent.updated"
    AGENT_UPDATE_REQUESTED          = "agent.update.requested"
    AGENT_UPDATE_FAILED             = "agent.update.failed"
    AGENT_AUTO_UPDATE_CHANGED       = "agent.auto_update.changed"

    # Server OS + DbInstance MSSQL metadata (migration 0015)
    SERVER_OS_DETECTED              = "server.os.detected"
    DBINSTANCE_METADATA_UPDATED     = "dbinstance.metadata.updated"


def _extract_source_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    xff = request.headers.get("X-Forwarded-For") or request.headers.get("X-Real-IP")
    if xff:
        return xff.split(",")[0].strip()
    return getattr(request.client, "host", None) if request.client else None


def _extract_user_agent(request: Request | None) -> str | None:
    if request is None:
        return None
    ua = request.headers.get("User-Agent")
    return ua[:500] if ua else None


def _coerce_uuid(value: UUID | str | None) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


async def log_event(
    db: AsyncSession,
    *,
    org_id: UUID | str | None = None,
    user_id: UUID | str | None = None,
    event_type: EventType | str,
    target_type: str | None = None,
    target_id: UUID | str | None = None,
    description: str = "",
    metadata: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditLog:
    """Create a single AuditLog row. Does NOT commit; caller decides.

    org_id/user_id may both be None (e.g. auth.login.failed for unknown user,
    or retention.* system events).

    The AuditLog table stores metadata as a JSON-serialized TEXT column
    (`metadata_json`). The `description` argument is folded into that JSON
    payload under the key `description` (truncated to 2000 chars) since the
    DB has no dedicated description column.
    """
    event_value = event_type.value if isinstance(event_type, EventType) else event_type

    payload: dict[str, Any] = {}
    if metadata:
        payload.update(metadata)
    if description:
        payload["description"] = description[:2000]

    entry = AuditLog(
        org_id=_coerce_uuid(org_id),
        user_id=_coerce_uuid(user_id),
        action=event_value,
        target_type=target_type[:50] if target_type else None,
        target_id=_coerce_uuid(target_id),
        metadata_json=json.dumps(payload, default=str) if payload else None,
        ip_address=_extract_source_ip(request),
        user_agent=_extract_user_agent(request),
    )
    db.add(entry)
    await db.flush()
    return entry
