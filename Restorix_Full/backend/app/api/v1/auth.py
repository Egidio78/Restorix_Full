import logging
from fastapi import APIRouter, Depends, HTTPException, Response, Cookie, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token, hash_password
from app.core.encryption import encrypt, decrypt
from app.schemas.auth import LoginRequest, TokenResponse, Require2FAResponse, TwoFAVerifyRequest, TwoFADisableRequest
from app.schemas.user import UserOut
from app.api.deps import get_current_user
from app.services.audit import log_event, EventType
from app.config import get_settings
import pyotp
import uuid
import io
import base64
import secrets
import qrcode

_logger = logging.getLogger(__name__)

# Pre-computed dummy hash to prevent timing attacks during login
# (always run bcrypt even when user doesn't exist)
_DUMMY_HASH = hash_password("dummy-timing-protection-value")

router = APIRouter()


def _cookie_opts() -> dict:
    settings = get_settings()
    return dict(httponly=True, samesite="lax", secure=settings.app_env != "development")


async def _safe_audit(db, **kwargs):
    """Best-effort audit log. Never raises — failures only warn."""
    try:
        await log_event(db, **kwargs)
        await db.commit()
    except Exception as audit_exc:
        _logger.warning("audit log failed: %s", audit_exc)


@router.post("/login")
async def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.email == payload.email, User.is_active == True)
    )
    user = result.scalar_one_or_none()

    # Always run bcrypt to prevent timing-based email enumeration
    password_ok = verify_password(payload.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not password_ok:
        await _safe_audit(
            db,
            org_id=user.org_id if user else None,
            user_id=user.id if user else None,
            event_type=EventType.AUTH_LOGIN_FAILED,
            description="Login failed (invalid credentials)",
            metadata={"email": payload.email, "reason": "invalid_credentials"},
            request=request,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # 2FA check
    if user.two_fa_enabled:
        if not payload.totp_code:
            return Require2FAResponse()
        if not user.two_fa_secret_enc:
            raise HTTPException(status_code=500, detail="2FA configuration error")
        secret = decrypt(user.two_fa_secret_enc)
        totp = pyotp.TOTP(secret)
        if not totp.verify(payload.totp_code, valid_window=1):
            await _safe_audit(
                db,
                org_id=user.org_id, user_id=user.id,
                event_type=EventType.AUTH_LOGIN_FAILED,
                description="Login failed (invalid 2FA code)",
                metadata={"email": payload.email, "reason": "invalid_2fa"},
                request=request,
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid 2FA code")

    settings = get_settings()
    access_token = create_access_token(subject=str(user.id), role=user.role)
    refresh_token = create_refresh_token(subject=str(user.id))

    cookie_opts = _cookie_opts()
    response.set_cookie(
        "access_token", access_token,
        max_age=settings.access_token_expire_minutes * 60,
        **cookie_opts
    )
    response.set_cookie(
        "refresh_token", refresh_token,
        max_age=settings.refresh_token_expire_days * 86400,
        **cookie_opts
    )

    await _safe_audit(
        db,
        org_id=user.org_id, user_id=user.id,
        event_type=EventType.AUTH_LOGIN_SUCCESS,
        description="Login success",
        metadata={"email": user.email},
        request=request,
    )

    return TokenResponse(access_token=access_token)


@router.post("/refresh")
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    payload = decode_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    try:
        user_uuid = uuid.UUID(payload["sub"])
    except (ValueError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    result = await db.execute(select(User).where(User.id == user_uuid, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    settings = get_settings()
    access_token = create_access_token(subject=str(user.id), role=user.role)
    response.set_cookie(
        "access_token", access_token,
        max_age=settings.access_token_expire_minutes * 60,
        **_cookie_opts()
    )

    return TokenResponse(access_token=access_token)


@router.post("/logout")
async def logout(
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    opts = _cookie_opts()
    response.delete_cookie("access_token", httponly=opts["httponly"], samesite=opts["samesite"], secure=opts["secure"])
    response.delete_cookie("refresh_token", httponly=opts["httponly"], samesite=opts["samesite"], secure=opts["secure"])
    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.AUTH_LOGOUT,
        description="Logout",
        request=request,
    )
    return {"message": "Logged out"}


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/2fa/setup")
async def setup_2fa(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a new TOTP secret, store it server-side as pending, and return QR code."""
    secret = pyotp.random_base32()
    settings = get_settings()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=current_user.email, issuer_name=settings.app_name)

    # Store pending secret server-side (encrypted) until user verifies
    current_user.pending_two_fa_secret_enc = encrypt(secret)
    db.add(current_user)
    await db.commit()

    # Generate QR code PNG as base64
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    qr_b64 = base64.b64encode(buf.read()).decode()

    return {"secret": secret, "qr_code": qr_b64}


@router.post("/2fa/verify")
async def verify_2fa(
    payload: TwoFAVerifyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Verify TOTP code against server-stored pending secret and enable 2FA."""
    if not current_user.pending_two_fa_secret_enc:
        raise HTTPException(status_code=400, detail="No pending 2FA setup. Call /2fa/setup first.")

    secret = decrypt(current_user.pending_two_fa_secret_enc)
    totp = pyotp.TOTP(secret)
    if not totp.verify(payload.code, valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid 2FA code")

    # Generate 8 backup codes (64-bit entropy each)
    backup_codes = [secrets.token_hex(8).upper() for _ in range(8)]

    current_user.two_fa_enabled = True
    current_user.two_fa_secret_enc = encrypt(secret)
    current_user.two_fa_backup_codes_enc = encrypt(",".join(backup_codes))
    current_user.pending_two_fa_secret_enc = None  # clear pending
    db.add(current_user)
    await db.commit()

    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.AUTH_2FA_ENABLED,
        description="2FA enabled",
        request=request,
    )

    return {"enabled": True, "backup_codes": backup_codes}


@router.post("/2fa/disable")
async def disable_2fa(
    payload: TwoFADisableRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Disable 2FA for the current user after password confirmation."""
    if not verify_password(payload.password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong password")

    current_user.two_fa_enabled = False
    current_user.two_fa_secret_enc = None
    current_user.two_fa_backup_codes_enc = None
    db.add(current_user)
    await db.commit()

    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.AUTH_2FA_DISABLED,
        description="2FA disabled",
        request=request,
    )

    return {"enabled": False}
