import pytest, json, argparse
import db
from unittest.mock import patch

class _Args:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)

def test_init_db(fresh_db):
    import manage
    manage.cmd_init_db(_Args())
    with db.get_db() as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "users" in tables

def test_create_user(fresh_db, monkeypatch):
    import manage
    monkeypatch.setattr("getpass.getpass", lambda _: "TestPassword1!")
    manage.cmd_create_user(_Args(username="testuser"))
    with db.get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE username='testuser'").fetchone()
    assert user is not None
    assert user["totp_secret_enc"] is not None
    codes = json.loads(user["recovery_codes"])
    assert len(codes) == 10

def test_list_users(fresh_db, capsys):
    import manage, bcrypt
    hashed = bcrypt.hashpw(b"pw", bcrypt.gensalt(rounds=4)).decode()
    with db.get_db() as conn:
        conn.execute("INSERT INTO users (username, password_hash) VALUES (?,?)", ("alice", hashed))
    manage.cmd_list_users(_Args())
    out = capsys.readouterr().out
    assert "alice" in out

def test_delete_user(fresh_db, monkeypatch):
    import manage, bcrypt
    hashed = bcrypt.hashpw(b"pw", bcrypt.gensalt(rounds=4)).decode()
    with db.get_db() as conn:
        conn.execute("INSERT INTO users (username, password_hash) VALUES (?,?)", ("bob", hashed))
    monkeypatch.setattr("builtins.input", lambda _: "s")
    manage.cmd_delete_user(_Args(username="bob"))
    with db.get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE username='bob'").fetchone()
    assert user is None

def test_set_password(fresh_db, monkeypatch):
    import manage, bcrypt
    old_hash = bcrypt.hashpw(b"old", bcrypt.gensalt(rounds=4)).decode()
    with db.get_db() as conn:
        conn.execute("INSERT INTO users (username, password_hash) VALUES (?,?)", ("carol", old_hash))
    monkeypatch.setattr("getpass.getpass", lambda _: "NewPass999!")
    manage.cmd_set_password(_Args(username="carol"))
    with db.get_db() as conn:
        user = conn.execute("SELECT password_hash FROM users WHERE username='carol'").fetchone()
    assert bcrypt.checkpw(b"NewPass999!", user["password_hash"].encode())
