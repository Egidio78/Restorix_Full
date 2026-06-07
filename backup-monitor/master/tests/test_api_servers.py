import hashlib, pytest
from fastapi.testclient import TestClient
import config

def _make_app():
    from fastapi import FastAPI
    from api.servers import router
    app = FastAPI(); app.include_router(router); return app

def _reg_key():
    return hashlib.sha256(f"{config.MASTER_SECRET}register".encode()).hexdigest()

@pytest.fixture
def client(fresh_db):
    return TestClient(_make_app())

def test_register_and_list(client):
    r = client.post("/api/v1/servers/register",
        json={"vps_id":"vps-001","hostname":"h1","cliente":"Test Srl","folders":["/home/Nativo"]},
        headers={"x-api-key": _reg_key()})
    assert r.status_code == 201
    assert "api_key" in r.json()

    r2 = client.get("/api/v1/servers")
    assert r2.status_code == 200
    assert len(r2.json()) == 1

def test_server_detail_not_found(client):
    r = client.get("/api/v1/servers/vps-999")
    assert r.status_code == 404

def test_register_unauthorized(client):
    r = client.post("/api/v1/servers/register",
        json={"vps_id":"vps-001","hostname":"h1"},
        headers={"x-api-key": "wrongkey"})
    assert r.status_code == 401

def test_server_detail_with_runs(client):
    import db
    # Register server
    client.post("/api/v1/servers/register",
        json={"vps_id":"vps-001","hostname":"h1","cliente":"Test"},
        headers={"x-api-key": _reg_key()})
    # Insert a backup run
    with db.get_db() as conn:
        conn.execute(
            "INSERT INTO backup_runs (vps_id,status,snapshot_id) VALUES (?,?,?)",
            ("vps-001","ok","snap-abc")
        )
    r = client.get("/api/v1/servers/vps-001")
    assert r.status_code == 200
    data = r.json()
    assert data["server"]["vps_id"] == "vps-001"
    assert len(data["runs"]) == 1
    assert data["runs"][0]["snapshot_id"] == "snap-abc"

def test_latest_snapshot(client):
    import db, hashlib, config
    client.post("/api/v1/servers/register",
        json={"vps_id":"vps-001","hostname":"h1"},
        headers={"x-api-key": _reg_key()})
    with db.get_db() as conn:
        conn.execute(
            "INSERT INTO backup_runs (vps_id,status,snapshot_id) VALUES (?,?,?)",
            ("vps-001","ok","snap-xyz")
        )
    api_key = hashlib.sha256(f"{config.MASTER_SECRET}vps-001".encode()).hexdigest()
    r = client.get("/api/v1/servers/vps-001/latest-snapshot",
        headers={"x-api-key": api_key})
    assert r.status_code == 200
    assert r.json()["snapshot_id"] == "snap-xyz"
