import logging
import uuid
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from app.database import get_db
from app.models.user import User, UserRole
from app.models.organization import Organization
from app.api.deps import get_current_user
from app.core.security import hash_password, verify_password
from app.schemas.user import UserOut
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


class UserInvite(BaseModel):
    email: EmailStr
    role: UserRole
    name: str | None = None


class UserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class UserInviteResponse(BaseModel):
    user: UserOut
    temporary_password: str


class OrgInfo(BaseModel):
    id: uuid.UUID
    name: str
    plan: str
    require_2fa: bool
    user_count: int


# Organization routes — must be defined BEFORE /{user_id} to avoid route conflict

class OrgUpdate(BaseModel):
    name: str | None = None
    require_2fa: bool | None = None


@router.get("/org/info", response_model=OrgInfo)
async def get_org_info(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current organization info."""
    org = await db.get(Organization, current_user.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    count_result = await db.execute(
        select(User).where(User.org_id == org.id, User.is_active == True)
    )
    user_count = len(count_result.scalars().all())
    return OrgInfo(
        id=org.id,
        name=org.name,
        plan=org.plan.value if hasattr(org.plan, "value") else str(org.plan),
        require_2fa=org.require_2fa,
        user_count=user_count,
    )


@router.patch("/org", response_model=OrgInfo)
async def update_org(
    payload: OrgUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update organization name / 2FA requirement. SuperAdmin and Admin only."""
    if current_user.role not in (UserRole.superadmin, UserRole.admin):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    org = await db.get(Organization, current_user.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    if payload.name is not None:
        org.name = payload.name
    if payload.require_2fa is not None:
        org.require_2fa = payload.require_2fa
    db.add(org)
    await db.commit()
    await db.refresh(org)
    count_result = await db.execute(
        select(User).where(User.org_id == org.id, User.is_active == True)
    )
    user_count = len(count_result.scalars().all())
    return OrgInfo(
        id=org.id,
        name=org.name,
        plan=org.plan.value if hasattr(org.plan, "value") else str(org.plan),
        require_2fa=org.require_2fa,
        user_count=user_count,
    )


@router.post("/me/change-password")
async def change_password_early(
    payload: PasswordChange,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Alias: defined early to avoid /{user_id} conflict."""
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
    current_user.password_hash = hash_password(payload.new_password)
    db.add(current_user)
    await db.commit()
    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.AUTH_PASSWORD_CHANGED,
        description="Password changed",
        request=request,
    )
    return {"message": "Password changed successfully"}


# User listing & management

@router.get("/", response_model=list[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all users in the current organization. Admin and SuperAdmin only."""
    if current_user.role not in (UserRole.superadmin, UserRole.admin):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await db.execute(
        select(User)
        .where(User.org_id == current_user.org_id)
        .order_by(User.created_at.desc())
    )
    return result.scalars().all()


@router.post("/invite", response_model=UserInviteResponse, status_code=201)
async def invite_user(
    payload: UserInvite,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new user with a temporary password. Admin and SuperAdmin only."""
    if current_user.role not in (UserRole.superadmin, UserRole.admin):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    if current_user.role == UserRole.admin and payload.role == UserRole.superadmin:
        raise HTTPException(status_code=403, detail="Admin cannot create SuperAdmin users")

    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    temp_password = secrets.token_urlsafe(12)

    user = User(
        org_id=current_user.org_id,
        email=payload.email,
        password_hash=hash_password(temp_password),
        role=payload.role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.USER_CREATED,
        target_type="user", target_id=str(user.id),
        description=f"Created user {user.email} (role={payload.role.value if hasattr(payload.role, 'value') else payload.role})",
        metadata={"email": user.email, "role": payload.role.value if hasattr(payload.role, "value") else str(payload.role)},
        request=request,
    )

    return UserInviteResponse(user=user, temporary_password=temp_password)


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a user's details."""
    user = await db.get(User, user_id)
    if not user or user.org_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id != current_user.id and current_user.role not in (UserRole.superadmin, UserRole.admin):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return user


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a user's role or active status. Admin and SuperAdmin only."""
    if current_user.role not in (UserRole.superadmin, UserRole.admin):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    user = await db.get(User, user_id)
    if not user or user.org_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot modify your own account")

    if current_user.role == UserRole.admin:
        if user.role == UserRole.superadmin:
            raise HTTPException(status_code=403, detail="Admin cannot modify SuperAdmin users")
        if payload.role == UserRole.superadmin:
            raise HTTPException(status_code=403, detail="Admin cannot promote to SuperAdmin")

    old_role = user.role
    role_changed = payload.role is not None and payload.role != old_role
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active

    db.add(user)
    await db.commit()
    await db.refresh(user)

    changed_fields = []
    if role_changed:
        changed_fields.append("role")
    if payload.is_active is not None:
        changed_fields.append("is_active")

    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.USER_UPDATED,
        target_type="user", target_id=str(user.id),
        description=f"Updated user {user.email}",
        metadata={"email": user.email, "fields_changed": changed_fields},
        request=request,
    )

    if role_changed:
        old_val = old_role.value if hasattr(old_role, "value") else str(old_role)
        new_val = payload.role.value if hasattr(payload.role, "value") else str(payload.role)
        await _safe_audit(
            db,
            org_id=current_user.org_id, user_id=current_user.id,
            event_type=EventType.USER_ROLE_CHANGED,
            target_type="user", target_id=str(user.id),
            description=f"Role changed for {user.email}: {old_val} -> {new_val}",
            metadata={"email": user.email, "from": old_val, "to": new_val},
            request=request,
        )

    return user


@router.delete("/{user_id}", status_code=204)
async def deactivate_user(
    user_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a user (sets is_active=False). Admin and SuperAdmin only."""
    if current_user.role not in (UserRole.superadmin, UserRole.admin):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    user = await db.get(User, user_id)
    if not user or user.org_id != current_user.org_id:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    if current_user.role == UserRole.admin and user.role == UserRole.superadmin:
        raise HTTPException(status_code=403, detail="Admin cannot deactivate SuperAdmin")

    user.is_active = False
    db.add(user)
    await db.commit()

    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.USER_DEACTIVATED,
        target_type="user", target_id=str(user.id),
        description=f"Deactivated user {user.email}",
        metadata={"email": user.email},
        request=request,
    )


# Self-service

@router.post("/me/change-password")
async def change_password(
    payload: PasswordChange,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change own password. Requires current password."""
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")

    current_user.password_hash = hash_password(payload.new_password)
    db.add(current_user)
    await db.commit()

    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.AUTH_PASSWORD_CHANGED,
        description="Password changed",
        request=request,
    )

    return {"message": "Password changed successfully"}


# Organization

@router.get("/org/info", response_model=OrgInfo)
async def get_org_info(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current organization info."""
    org = await db.get(Organization, current_user.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    count_result = await db.execute(
        select(User).where(User.org_id == org.id, User.is_active == True)
    )
    user_count = len(count_result.scalars().all())

    return OrgInfo(
        id=org.id,
        name=org.name,
        plan=org.plan.value if hasattr(org.plan, "value") else str(org.plan),
        require_2fa=org.require_2fa,
        user_count=user_count,
    )


class OrgUpdate(BaseModel):
    name: str | None = None
    require_2fa: bool | None = None


@router.patch("/org", response_model=OrgInfo)
async def update_org(
    payload: OrgUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update organization settings. SuperAdmin and Admin only."""
    if current_user.role not in (UserRole.superadmin, UserRole.admin):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    org = await db.get(Organization, current_user.org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    if payload.name is not None:
        org.name = payload.name
    if payload.require_2fa is not None:
        org.require_2fa = payload.require_2fa

    db.add(org)
    await db.commit()
    await db.refresh(org)

    count_result = await db.execute(
        select(User).where(User.org_id == org.id, User.is_active == True)
    )
    user_count = len(count_result.scalars().all())

    return OrgInfo(
        id=org.id,
        name=org.name,
        plan=org.plan.value if hasattr(org.plan, "value") else str(org.plan),
        require_2fa=org.require_2fa,
        user_count=user_count,
    )
