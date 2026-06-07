import time
import auth.sessions as sessions
import db

def _create_user(username="admin"):
    with db.get_db() as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?,?)",
            (username, "hash")
        )
        return conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()["id"]

def test_create_and_get_session(fresh_db):
    uid = _create_user()
    token = sessions.create_session(uid)
    user = sessions.get_session_user(token)
    assert user is not None
    assert user["username"] == "admin"

def test_invalid_token_returns_none(fresh_db):
    assert sessions.get_session_user("badtoken") is None

def test_revoke_session(fresh_db):
    uid = _create_user()
    token = sessions.create_session(uid)
    sessions.revoke_session(token)
    assert sessions.get_session_user(token) is None
