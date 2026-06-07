import os, pytest
os.environ.setdefault("MASTER_SECRET", "testsecret")
os.environ.setdefault("JWT_SECRET", "testjwt")
os.environ.setdefault("TOTP_ENCRYPTION_KEY", "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ=")

import db

def test_init_db_creates_tables(tmp_path):
    import config
    config.DB_PATH = str(tmp_path / "test.db")
    db.init_db()
    conn = db.get_db()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"servers", "backup_runs", "restore_runs", "users", "sessions"} <= tables
