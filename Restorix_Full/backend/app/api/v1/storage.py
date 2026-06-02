import logging
import uuid
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.storage import StorageDestination
from app.models.user import User
from app.schemas.storage import StorageCreate, StorageOut, StorageTestResult
from app.api.deps import get_current_user
from app.core.encryption import encrypt, decrypt
from app.services.audit import log_event, EventType
from pydantic import BaseModel

_logger = logging.getLogger(__name__)

router = APIRouter()


async def _safe_audit(db, **kwargs):
    """Best-effort audit log. Never raises — failures only warn."""
    try:
        await log_event(db, **kwargs)
        await db.commit()
    except Exception as audit_exc:
        _logger.warning("audit log failed: %s", audit_exc)


class StorageUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None


def _org_id(user: User) -> uuid.UUID:
    return user.org_id


@router.get("/", response_model=list[StorageOut])
async def list_storage(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(StorageDestination)
        .where(StorageDestination.org_id == _org_id(current_user), StorageDestination.is_active == True)
        .order_by(StorageDestination.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=StorageOut, status_code=201)
async def create_storage(
    payload: StorageCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("superadmin", "admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    dest = StorageDestination(
        org_id=_org_id(current_user),
        name=payload.name,
        storage_type=payload.storage_type,
        config_enc=encrypt(json.dumps(payload.config)),
    )
    db.add(dest)
    await db.commit()
    await db.refresh(dest)

    st = dest.storage_type.value if hasattr(dest.storage_type, "value") else str(dest.storage_type)
    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.STORAGE_CREATED,
        target_type="storage_destination", target_id=str(dest.id),
        description=f"Created storage destination {dest.name} ({st})",
        metadata={"name": dest.name, "storage_type": st},
        request=request,
    )

    return dest


@router.get("/{dest_id}", response_model=StorageOut)
async def get_storage(
    dest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dest = await db.get(StorageDestination, dest_id)
    if not dest or dest.org_id != _org_id(current_user) or not dest.is_active:
        raise HTTPException(status_code=404, detail="Storage destination not found")
    return dest


@router.patch("/{dest_id}", response_model=StorageOut)
async def update_storage(
    dest_id: uuid.UUID,
    payload: StorageUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("superadmin", "admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    dest = await db.get(StorageDestination, dest_id)
    if not dest or dest.org_id != _org_id(current_user) or not dest.is_active:
        raise HTTPException(status_code=404, detail="Storage destination not found")
    if payload.name is not None:
        dest.name = payload.name
    if payload.config is not None:
        existing = {}
        try:
            existing = json.loads(decrypt(dest.config_enc))
        except Exception:
            pass
        merged = {**existing, **payload.config}
        dest.config_enc = encrypt(json.dumps(merged))
        dest.last_tested_at = None
        dest.last_test_ok = None
    db.add(dest)
    await db.commit()
    await db.refresh(dest)

    changed = []
    if payload.name is not None:
        changed.append("name")
    if payload.config is not None:
        changed.append("config")
    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.STORAGE_UPDATED,
        target_type="storage_destination", target_id=str(dest.id),
        description=f"Updated storage destination {dest.name}",
        metadata={"name": dest.name, "fields_changed": changed},
        request=request,
    )

    return dest


@router.get("/{dest_id}/config", response_model=dict)
async def get_storage_config(
    dest_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns the decrypted config for editing. Password fields are masked."""
    if current_user.role not in ("superadmin", "admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    dest = await db.get(StorageDestination, dest_id)
    if not dest or dest.org_id != _org_id(current_user):
        raise HTTPException(status_code=404, detail="Storage destination not found")
    try:
        cfg = json.loads(decrypt(dest.config_enc))
    except Exception:
        cfg = {}
    for key in ("secret_key", "password", "client_secret", "credentials_json"):
        if cfg.get(key):
            cfg[key] = ""
    return cfg


@router.delete("/{dest_id}", status_code=204)
async def delete_storage(
    dest_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    dest = await db.get(StorageDestination, dest_id)
    if not dest or dest.org_id != _org_id(current_user):
        raise HTTPException(status_code=404, detail="Storage destination not found")
    dest.is_active = False
    db.add(dest)
    await db.commit()

    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.STORAGE_DELETED,
        target_type="storage_destination", target_id=str(dest.id),
        description=f"Deleted storage destination {dest.name}",
        metadata={"name": dest.name},
        request=request,
    )


@router.post("/{dest_id}/test", response_model=StorageTestResult)
async def test_storage(
    dest_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    dest = await db.get(StorageDestination, dest_id)
    if not dest or dest.org_id != _org_id(current_user) or not dest.is_active:
        raise HTTPException(status_code=404, detail="Storage destination not found")

    try:
        config = json.loads(decrypt(dest.config_enc))
        ok = bool(config)
        msg = "Configurazione valida. Test connessione reale disponibile con agente installato."
    except Exception as e:
        ok = False
        msg = f"Errore configurazione: {str(e)}"

    dest.last_tested_at = datetime.now(timezone.utc)
    dest.last_test_ok = ok
    db.add(dest)
    await db.commit()

    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.STORAGE_TESTED,
        target_type="storage_destination", target_id=str(dest.id),
        description=f"Tested storage destination {dest.name}: {'ok' if ok else 'error'}",
        metadata={"name": dest.name, "result": "ok" if ok else "error"},
        request=request,
    )

    return StorageTestResult(ok=ok, message=msg)
