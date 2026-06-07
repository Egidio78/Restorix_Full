import hashlib, pytest
from fastapi.testclient import TestClient
import config, db

def _make_app():
    from fastapi import FastAPI
    from api.backup import router
    app = FastAPI()
    app.include_router(router)
    return app

def _api_key(vps_id):
    return hashlib.sha256(f"{config.MASTER_SECRET}{vps_id}".encode()).hexdigest()

@pytest.fixture
def client(fresh_db):
    with db.get_db() as conn:
        conn.execute(
            "INSERT INTO servers (vps_id,hostname,cliente,api_key) VALUES (?,?,?,?)",
            ("vps-001", "test.host", "Test Srl", _api_key("vps-001"))
        )
    return TestClient(_make_app())

def test_backup_report_ok(client):
    r = client.post("/api/v1/backup/report",
        json={"vps_id":"vps-001","status":"ok","size_gb":4.2,"snapshot_id":"abc123"},
        headers={"x-api-key": _api_key("vps-001")})
    assert r.status_code == 204

def test_backup_report_wrong_key(client):
    r = client.post("/api/v1/backup/report",
        json={"vps_id":"vps-001","status":"ok"},
        headers={"x-api-key": "wrongkey"})
    assert r.status_code == 401

def test_backup_report_unknown_vps(client):
    r = client.post("/api/v1/backup/report",
        json={"vps_id":"vps-999","status":"ok"},
        headers={"x-api-key": _api_key("vps-999")})
    assert r.status_code == 404
