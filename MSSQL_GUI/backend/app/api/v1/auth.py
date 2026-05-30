from fastapi import APIRouter, Depends, HTTPException, Response, Cookie, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.core.security import verify_password, create_access_token, create_refresh_token, decode_token, hash_password
from app.schemas.auth import LoginRequest, TokenResponse, Require2FAResponse
from app.schemas.user import UserOut
from app.api.deps import get_current_user
from app.config import get_settings
import pyotp
import uuid

# Pre-computed dummy hash to prevent timing attacks during login
# (always run bcrypt even when user doesn't exist)
_DUMMY_HASH = hash_password("dummy-timing-protection-value")

router = APIRouter()


def _cookie_opts() -> dict:
    settings = get_settings()
    return dict(httponly=True, samesite="lax", secure=settings.app_env != "development")


@router.post("/login")
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.email == payload.email, User.is_active == True)
    )
    user = result.scalar_one_or_none()

    # Always run bcrypt to prevent timing-based email enumeration
    password_ok = verify_password(payload.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not password_ok:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    # 2FA check
    if user.two_fa_enabled:
        if not payload.totp_code:
            return Require2FAResponse()
        from app.core.encryption import decrypt
        if not user.two_fa_secret_enc:
            raise HTTPException(status_code=500, detail="2FA configuration error")
        secret = decrypt(user.two_fa_secret_enc)
        totp = pyotp.TOTP(secret)
        if not totp.verify(payload.totp_code, valid_window=1):
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
async def logout(response: Response):
    opts = _cookie_opts()
    response.delete_cookie("access_token", httponly=opts["httponly"], samesite=opts["samesite"], secure=opts["secure"])
    response.delete_cookie("refresh_token", httponly=opts["httponly"], samesite=opts["samesite"], secure=opts["secure"])
    return {"message": "Logged out"}


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
