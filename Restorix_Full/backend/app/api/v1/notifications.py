import uuid
import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.notification import NotificationChannel
from app.models.user import User
from app.schemas.notification import NotificationChannelCreate, NotificationChannelOut
from app.api.deps import get_current_user
from app.core.encryption import encrypt, decrypt

router = APIRouter()


@router.get("/", response_model=list[NotificationChannelOut])
async def list_channels(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(NotificationChannel)
        .where(NotificationChannel.org_id == current_user.org_id)
        .order_by(NotificationChannel.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=NotificationChannelOut, status_code=201)
async def create_channel(
    payload: NotificationChannelCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    channel = NotificationChannel(
        org_id=current_user.org_id,
        name=payload.name,
        channel_type=payload.channel_type,
        config_enc=encrypt(json.dumps(payload.config)),
        on_success=payload.on_success,
        on_failure=payload.on_failure,
        enabled=payload.enabled,
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    return channel


@router.delete("/{channel_id}", status_code=204)
async def delete_channel(
    channel_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    ch = await db.get(NotificationChannel, channel_id)
    if not ch or ch.org_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Channel not found")
    await db.delete(ch)
    await db.commit()


@router.patch("/{channel_id}/toggle", response_model=NotificationChannelOut)
async def toggle_channel(
    channel_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    ch = await db.get(NotificationChannel, channel_id)
    if not ch or ch.org_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="Channel not found")
    ch.enabled = not ch.enabled
    db.add(ch)
    await db.commit()
    await db.refresh(ch)
    return ch
