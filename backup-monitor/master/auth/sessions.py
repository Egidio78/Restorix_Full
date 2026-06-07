import secrets, hashlib
from datetime import datetime, timedelta
import db, config

SESSION_DURATION_HOURS = 8

def create_session(user_id: int) -> str:
    token = secrets.token_hex(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires_at = (datetime.utcnow() + timedelta(hours=SESSION_DURATION_HOURS)).isoformat()
    with db.get_db() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?,?,?)",
            (token_hash, user_id, expires_at)
        )
    return token

def get_session_user(token: str) -> dict | None:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with db.get_db() as conn:
        row = conn.execute(
            """SELECT s.expires_at, s.revoked,
                      u.id, u.username, u.totp_secret_enc as totp_secret
               FROM sessions s JOIN users u ON u.id = s.user_id
               WHERE s.token=?""",
            (token_hash,)
        ).fetchone()
    if not row:
        return None
    if row["revoked"]:
        return None
    if datetime.fromisoformat(row["expires_at"]) < datetime.utcnow():
        return None
    return dict(row)

def revoke_session(token: str) -> None:
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with db.get_db() as conn:
        conn.execute("UPDATE sessions SET revoked=1 WHERE token=?", (token_hash,))
