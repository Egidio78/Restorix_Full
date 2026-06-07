import hashlib, pytest
from fastapi.testclient import TestClient
import config, db

def _make_app():
    from fastapi import FastAPI
    from api.restore import router
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

def test_restore_report_ok(client):
    r = client.post("/api/v1/restore/report",
        json={"vps_id": "vps-001", "status": "ok", "checksum_ok": 1, "duration_s": 45},
        headers={"x-api-key": _api_key("vps-001")})
    assert r.status_code == 204

def test_restore_report_wrong_key(client):
    r = client.post("/api/v1/restore/report",
        json={"vps_id": "vps-001", "status": "ok"},
        headers={"x-api-key": "wrongkey"})
    assert r.status_code == 401

def test_restore_links_to_latest_backup_run(client):
    # First insert a backup run
    with db.get_db() as conn:
        conn.execute(
            "INSERT INTO backup_runs (vps_id, status) VALUES (?, ?)",
            ("vps-001", "ok")
        )
        backup_run_id = conn.execute(
            "SELECT id FROM backup_runs WHERE vps_id='vps-001' ORDER BY id DESC LIMIT 1"
        ).fetchone()["id"]

    r = client.post("/api/v1/restore/report",
        json={"vps_id": "vps-001", "status": "ok", "checksum_ok": 1},
        headers={"x-api-key": _api_key("vps-001")})
    assert r.status_code == 204

    with db.get_db() as conn:
        restore = conn.execute(
            "SELECT backup_run_id FROM restore_runs WHERE vps_id='vps-001' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert restore["backup_run_id"] == backup_run_id

def test_restore_report_unknown_vps(fresh_db):
    client = TestClient(_make_app())
    r = client.post("/api/v1/restore/report",
        json={"vps_id": "vps-999", "status": "ok"},
        headers={"x-api-key": _api_key("vps-999")})
    assert r.status_code == 404

def test_restore_report_no_backup_run(client):
    # No backup runs exist; backup_run_id should be NULL
    r = client.post("/api/v1/restore/report",
        json={"vps_id": "vps-001", "status": "ok"},
        headers={"x-api-key": _api_key("vps-001")})
    assert r.status_code == 204

    with db.get_db() as conn:
        restore = conn.execute(
            "SELECT backup_run_id FROM restore_runs WHERE vps_id='vps-001'"
        ).fetchone()
    assert restore["backup_run_id"] is None
