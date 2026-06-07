import os, pytest
os.environ.setdefault("MASTER_SECRET", "testsecret")
os.environ.setdefault("JWT_SECRET", "testjwt")
os.environ.setdefault("TOTP_ENCRYPTION_KEY", "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ=")
os.environ.setdefault("DB_PATH", ":memory:")

import db

@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
