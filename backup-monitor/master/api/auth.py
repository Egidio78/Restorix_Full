import json
from datetime import datetime, timedelta
from collections import defaultdict
from fastapi import APIRouter, HTTPException, Cookie, Response
from pydantic import BaseModel
import bcrypt
import db, config
from auth.sessions import create_session, get_session_user, revoke_session
from auth.totp import verify_totp, generate_totp_secret, encrypt_secret, generate_qr_b64, generate_recovery_codes

router = APIRouter()

# Simple in-memory rate limiter: track failed attempts per username
_failed_attempts: dict[str, list[datetime]] = defaultdict(list)
RATE_LIMIT_WINDOW = timedelta(minutes=10)
RATE_LIMIT_MAX = 5

def _check_rate_limit(username: str):
    now = datetime.utcnow()
    attempts = [t for t in _failed_attempts[username] if now - t < RATE_LIMIT_WINDOW]
    _failed_attempts[username] = attempts
    if len(attempts) >= RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail="Troppi tentativi. Riprova tra 10 minuti.")

def _record_failed(username: str):
    _failed_attempts[username].append(datetime.utcnow())

class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: str

@router.post("/api/v1/auth/login")
def login(payload: LoginRequest, response: Response):
    _check_rate_limit(payload.username)
    with db.get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE username=?", (payload.username,)).fetchone()
    if not user:
        _record_failed(payload.username)
        raise HTTPException(status_code=401, detail="Credenziali non valide")
    if not bcrypt.checkpw(payload.password.encode(), user["password_hash"].encode()):
        _record_failed(payload.username)
        raise HTTPException(status_code=401, detail="Credenziali non valide")
    if user["totp_secret_enc"]:
        if not verify_totp(user["totp_secret_enc"], payload.totp_code):
            _record_failed(payload.username)
            raise HTTPException(status_code=401, detail="Codice 2FA non valido")
    token = create_session(user["id"])
    response.set_cookie("session", token, httponly=True, samesite="strict", max_age=8*3600)
    return {"ok": True}

@router.post("/api/v1/auth/logout", status_code=204)
def logout(response: Response, session: str | None = Cookie(default=None)):
    if session:
        revoke_session(session)
    response.delete_cookie("session")

@router.get("/api/v1/auth/me")
def me(session: str | None = Cookie(default=None)):
    if not session:
        raise HTTPException(status_code=401, detail="Non autenticato")
    user = get_session_user(session)
    if not user:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    return {"username": user["username"], "role": user["role"] if "role" in user.keys() else "admin"}
