import bcrypt, pytest
from fastapi.testclient import TestClient
import db

def _make_app():
    from fastapi import FastAPI
    from api.auth import router
    app = FastAPI(); app.include_router(router); return app

@pytest.fixture
def client(fresh_db):
    # Clear rate limit state between tests
    from api.auth import _failed_attempts
    _failed_attempts.clear()
    return TestClient(_make_app())

def _insert_user(password="secret", totp_secret_enc=None):
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()
    with db.get_db() as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, totp_secret_enc) VALUES (?,?,?)",
            ("admin", hashed, totp_secret_enc)
        )

def test_login_no_totp(client):
    _insert_user()
    r = client.post("/api/v1/auth/login",
        json={"username": "admin", "password": "secret", "totp_code": ""})
    assert r.status_code == 200
    assert "session" in r.cookies

def test_login_wrong_password(client):
    _insert_user()
    r = client.post("/api/v1/auth/login",
        json={"username": "admin", "password": "wrong", "totp_code": ""})
    assert r.status_code == 401

def test_login_unknown_user(client):
    r = client.post("/api/v1/auth/login",
        json={"username": "nobody", "password": "secret", "totp_code": ""})
    assert r.status_code == 401

def test_logout(client):
    _insert_user()
    r = client.post("/api/v1/auth/login",
        json={"username": "admin", "password": "secret", "totp_code": ""})
    assert r.status_code == 200
    r2 = client.post("/api/v1/auth/logout")
    assert r2.status_code == 204

def test_me_authenticated(client):
    _insert_user()
    client.post("/api/v1/auth/login",
        json={"username": "admin", "password": "secret", "totp_code": ""})
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200
    assert r.json()["username"] == "admin"

def test_me_unauthenticated(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401

def test_rate_limit(client):
    _insert_user()
    for _ in range(5):
        client.post("/api/v1/auth/login",
            json={"username": "admin", "password": "wrong", "totp_code": ""})
    r = client.post("/api/v1/auth/login",
        json={"username": "admin", "password": "wrong", "totp_code": ""})
    assert r.status_code == 429
