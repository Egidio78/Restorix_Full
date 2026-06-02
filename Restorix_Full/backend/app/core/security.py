from datetime import datetime, timedelta, timezone
from typing import Any
import jwt
import bcrypt
from app.config import get_settings


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def _secret_key() -> str:
    return get_settings().secret_key.get_secret_value()


def create_access_token(subject: str, role: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": subject,
        "role": role,
        "type": "access",
        "exp": expire,
    }
    return jwt.encode(payload, _secret_key(), algorithm="HS256")


def create_refresh_token(subject: str) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    payload = {
        "sub": subject,
        "type": "refresh",
        "exp": expire,
    }
    return jwt.encode(payload, _secret_key(), algorithm="HS256")


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, _secret_key(), algorithms=["HS256"])
    except jwt.exceptions.InvalidTokenError:
        return None
