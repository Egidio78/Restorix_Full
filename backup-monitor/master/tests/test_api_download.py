import hashlib, time, pytest
import jwt
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import db, config

def _make_app():
    from fastapi import FastAPI
    from api.download import router
    app = FastAPI(); app.include_router(router); return app

@pytest.fixture
def client_and_token(fresh_db):
    # Insert a user and create a real session
    import bcrypt
    from auth.sessions import create_session
    hashed = bcrypt.hashpw(b"secret", bcrypt.gensalt(rounds=4)).decode()
    with db.get_db() as conn:
        conn.execute("INSERT INTO users (username, password_hash) VALUES (?,?)", ("admin", hashed))
        uid = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()["id"]
    session_token = create_session(uid)
    app = _make_app()
    client = TestClient(app, cookies={"session": session_token})
    # Register a VPS
    import hashlib
    api_key = hashlib.sha256(f"{config.MASTER_SECRET}vps-001".encode()).hexdigest()
    with db.get_db() as conn:
        conn.execute(
            "INSERT INTO servers (vps_id, hostname, api_key) VALUES (?,?,?)",
            ("vps-001", "host1", api_key)
        )
    return client

def test_download_unauthenticated(fresh_db):
    app = _make_app()
    client = TestClient(app)
    r = client.get("/api/v1/servers/vps-001/snapshots/snap-abc/download")
    assert r.status_code == 401

def test_download_vps_not_found(client_and_token):
    r = client_and_token.get("/api/v1/servers/vps-999/snapshots/snap-abc/download")
    assert r.status_code == 404

def test_jwt_token_generation_and_decode():
    from api.download import _generate_download_token, _decode_download_token
    token = _generate_download_token("vps-001", "snap-abc", None)
    payload = _decode_download_token(token)
    assert payload["vps_id"] == "vps-001"
    assert payload["snapshot_id"] == "snap-abc"

def test_jwt_token_expired():
    from api.download import _decode_download_token
    from fastapi import HTTPException
    payload = {"vps_id": "vps-001", "snapshot_id": "snap-abc", "folder": None, "exp": int(time.time()) - 10}
    token = jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")
    with pytest.raises(HTTPException) as exc:
        _decode_download_token(token)
    assert exc.value.status_code == 410

def test_large_file_returns_jwt_link(client_and_token):
    # Insert a backup run with large size
    with db.get_db() as conn:
        conn.execute(
            "INSERT INTO backup_runs (vps_id, status, snapshot_id, size_gb) VALUES (?,?,?,?)",
            ("vps-001", "ok", "snap-big", 10.0)
        )
    r = client_and_token.get("/api/v1/servers/vps-001/snapshots/snap-big/download")
    assert r.status_code == 200
    data = r.json()
    assert data["type"] == "large_file"
    assert "download_url" in data
