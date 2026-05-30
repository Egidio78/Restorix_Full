import pytest
import pyotp
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.organization import Organization, OrgPlan
from app.models.user import User, UserRole
from app.core.security import hash_password
from app.core.encryption import encrypt, decrypt


@pytest.fixture
async def authenticated_client(client: AsyncClient, db_session: AsyncSession):
    """A client logged in as a fresh user with no 2FA."""
    org = Organization(name="2FA Test Org", plan=OrgPlan.saas_starter)
    db_session.add(org)
    await db_session.flush()
    user = User(
        org_id=org.id,
        email="twofa_user@example.com",
        password_hash=hash_password("pass123"),
        role=UserRole.admin,
    )
    db_session.add(user)
    await db_session.commit()

    await client.post("/api/v1/auth/login", json={"email": "twofa_user@example.com", "password": "pass123"})
    return client, user


async def test_setup_2fa_returns_secret_and_qr(authenticated_client):
    client, _ = authenticated_client
    response = await client.post("/api/v1/auth/2fa/setup")
    assert response.status_code == 200
    data = response.json()
    assert "secret" in data
    assert "qr_code" in data
    # secret must be a valid base32 string
    assert len(data["secret"]) >= 16
    # qr_code must be a valid base64 PNG
    import base64
    decoded = base64.b64decode(data["qr_code"])
    assert decoded[:4] == b"\x89PNG"


async def test_verify_2fa_enables_it(authenticated_client, db_session: AsyncSession):
    client, user = authenticated_client
    setup = await client.post("/api/v1/auth/2fa/setup")
    secret = setup.json()["secret"]

    totp = pyotp.TOTP(secret)
    code = totp.now()
    response = await client.post("/api/v1/auth/2fa/verify", json={"code": code, "secret": secret})
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert "backup_codes" in data
    assert len(data["backup_codes"]) == 8

    # Reload user from DB and confirm 2FA is saved
    await db_session.refresh(user)
    assert user.two_fa_enabled is True
    assert user.two_fa_secret_enc is not None
    # Decrypt and verify secret matches
    assert decrypt(user.two_fa_secret_enc) == secret


async def test_verify_2fa_wrong_code_returns_400(authenticated_client):
    client, _ = authenticated_client
    response = await client.post("/api/v1/auth/2fa/verify", json={
        "code": "000000",
        "secret": pyotp.random_base32(),
    })
    assert response.status_code == 400


async def test_disable_2fa_correct_password(authenticated_client, db_session: AsyncSession):
    client, user = authenticated_client
    # Enable 2FA first
    setup = await client.post("/api/v1/auth/2fa/setup")
    secret = setup.json()["secret"]
    totp = pyotp.TOTP(secret)
    await client.post("/api/v1/auth/2fa/verify", json={"code": totp.now(), "secret": secret})

    # Disable it
    response = await client.post("/api/v1/auth/2fa/disable", json={"password": "pass123"})
    assert response.status_code == 200
    assert response.json()["enabled"] is False

    # Reload and confirm
    await db_session.refresh(user)
    assert user.two_fa_enabled is False
    assert user.two_fa_secret_enc is None


async def test_disable_2fa_wrong_password_returns_401(authenticated_client):
    client, _ = authenticated_client
    response = await client.post("/api/v1/auth/2fa/disable", json={"password": "wrongpass"})
    assert response.status_code == 401


async def test_setup_2fa_requires_auth(client: AsyncClient):
    """Unauthenticated user cannot access 2FA setup."""
    response = await client.post("/api/v1/auth/2fa/setup")
    assert response.status_code == 401
