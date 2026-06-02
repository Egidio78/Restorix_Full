import logging
import os
import shutil
import uuid as _uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.deps import get_current_user
from app.models.organization import Organization
from app.models.user import User, UserRole
from app.schemas.organization import (
    OrganizationSettingsUpdate,
    OrganizationSettingsOut,
    VerifyTempdirRequest,
    VerifyTempdirResponse,
)
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


@router.patch("/me/settings", response_model=OrganizationSettingsOut)
async def update_my_org_settings(
    payload: OrganizationSettingsUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update retention/scheduling settings for the current organization.
    SuperAdmin and Admin only.
    """
    if current_user.role not in (UserRole.superadmin, UserRole.admin):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    org = await db.get(Organization, current_user.org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(org, k, v)

    db.add(org)
    await db.commit()
    await db.refresh(org)

    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.ORG_SETTINGS_UPDATED,
        target_type="organization", target_id=str(org.id),
        description=f"Updated organization settings ({', '.join(data.keys()) or 'no fields'})",
        metadata={"fields_changed": list(data.keys())},
        request=request,
    )

    return OrganizationSettingsOut(
        id=org.id,
        audit_retention_days=org.audit_retention_days,
        schedule_cleanup_cron=org.schedule_cleanup_cron,
        require_2fa=org.require_2fa,
        restore_temp_dir=org.restore_temp_dir,
        ui_theme=org.ui_theme,
    )


@router.get("/me/settings", response_model=OrganizationSettingsOut)
async def get_my_org_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Read retention/scheduling settings for the current organization."""
    org = await db.get(Organization, current_user.org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return OrganizationSettingsOut(
        id=org.id,
        audit_retention_days=org.audit_retention_days,
        schedule_cleanup_cron=org.schedule_cleanup_cron,
        require_2fa=org.require_2fa,
        restore_temp_dir=org.restore_temp_dir,
        ui_theme=org.ui_theme,
    )


@router.post("/me/settings/verify-tempdir", response_model=VerifyTempdirResponse)
async def verify_tempdir(
    payload: VerifyTempdirRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Verify that a given path is a writable directory accessible from the API container.
    Returns free disk space when accessible. SuperAdmin and Admin only.
    """
    if current_user.role not in (UserRole.superadmin, UserRole.admin):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    path = payload.path

    def _compute() -> VerifyTempdirResponse:
        # Path traversal guard
        if ".." in path or not path.startswith("/"):
            return VerifyTempdirResponse(
                ok=False,
                message="Path non valido (deve essere assoluto, no '..').",
            )

        p = Path(path)
        if not p.exists():
            return VerifyTempdirResponse(
                ok=False,
                message=f"La cartella `{path}` non esiste nel container API.",
            )
        if not p.is_dir():
            return VerifyTempdirResponse(
                ok=False,
                message=f"`{path}` esiste ma non è una cartella.",
            )
        if not os.access(str(p), os.W_OK):
            return VerifyTempdirResponse(
                ok=False,
                message=f"La cartella `{path}` non è scrivibile dall'utente del container.",
            )

        test_file = p / f"dbshield-write-test-{_uuid.uuid4().hex}.tmp"
        try:
            test_file.write_text("test")
            test_file.unlink()
        except Exception as e:
            return VerifyTempdirResponse(
                ok=False,
                message=f"Errore di scrittura: {e}",
            )

        usage = shutil.disk_usage(str(p))
        free_gb = usage.free / (1024 ** 3)
        return VerifyTempdirResponse(
            ok=True,
            free_gb=round(free_gb, 2),
            message=f"Cartella scrivibile. {free_gb:.2f} GB liberi.",
        )

    result = _compute()

    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.ORG_SETTINGS_TEMPDIR_VERIFIED,
        target_type="organization", target_id=str(current_user.org_id),
        description=f"Verified tempdir {path}: {'ok' if result.ok else 'fail'}",
        metadata={"path": path, "ok": bool(result.ok), "free_gb": result.free_gb},
        request=request,
    )

    return result
