import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.organization import Organization, OrgPlan
from app.models.user import User, UserRole
from app.core.security import hash_password
from app.core.encryption import encrypt
import pyotp


@pytest.fixture
async def org_and_user(db_session: AsyncSession):
    org = Organization(name="Test Org", plan=OrgPlan.saas_starter)
    db_session.add(org)
    await db_session.flush()

    user = User(
        org_id=org.id,
        email="test@example.com",
        password_hash=hash_password("password123"),
        role=UserRole.admin,
    )
    db_session.add(user)
    await db_session.commit()
    return org, user


async def test_login_success(client: AsyncClient, org_and_user):
    response = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "password123",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert response.cookies.get("access_token") is not None
    assert response.cookies.get("refresh_token") is not None


async def test_login_wrong_password(client: AsyncClient, org_and_user):
    response = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "wrongpassword",
    })
    assert response.status_code == 401


async def test_login_nonexistent_user(client: AsyncClient):
    response = await client.post("/api/v1/auth/login", json={
        "email": "ghost@example.com",
        "password": "any",
    })
    assert response.status_code == 401


async def test_me_authenticated(client: AsyncClient, org_and_user):
    login = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "password123",
    })
    assert login.status_code == 200

    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"


async def test_me_unauthenticated(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_logout(client: AsyncClient, org_and_user):
    await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "password123",
    })
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 200


async def test_login_requires_2fa_returns_require_2fa_response(client: AsyncClient, db_session: AsyncSession):
    """Login with 2FA user but no totp_code returns Require2FAResponse, not 401"""
    org = Organization(name="2FA Test Org", plan=OrgPlan.saas_starter)
    db_session.add(org)
    await db_session.flush()
    secret = pyotp.random_base32()
    user = User(
        org_id=org.id,
        email="twofa_login@example.com",
        password_hash=hash_password("pass123"),
        role=UserRole.admin,
        two_fa_enabled=True,
        two_fa_secret_enc=encrypt(secret),
    )
    db_session.add(user)
    await db_session.commit()

    response = await client.post("/api/v1/auth/login", json={
        "email": "twofa_login@example.com",
        "password": "pass123",
    })
    assert response.status_code == 200
    assert response.json()["require_2fa"] is True


async def test_refresh_with_valid_token(client: AsyncClient, db_session: AsyncSession):
    """POST /refresh with a valid refresh cookie issues a new access token"""
    org = Organization(name="Refresh Org", plan=OrgPlan.saas_starter)
    db_session.add(org)
    await db_session.flush()
    user = User(
        org_id=org.id,
        email="refresh@example.com",
        password_hash=hash_password("pass123"),
        role=UserRole.viewer,
    )
    db_session.add(user)
    await db_session.commit()

    await client.post("/api/v1/auth/login", json={"email": "refresh@example.com", "password": "pass123"})
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_refresh_without_cookie_returns_401(client: AsyncClient):
    """POST /refresh without a refresh cookie returns 401"""
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


async def test_login_inactive_user_returns_401(client: AsyncClient, db_session: AsyncSession):
    """Inactive user cannot log in"""
    org = Organization(name="Inactive Org", plan=OrgPlan.saas_starter)
    db_session.add(org)
    await db_session.flush()
    user = User(
        org_id=org.id,
        email="inactive@example.com",
        password_hash=hash_password("pass123"),
        role=UserRole.viewer,
        is_active=False,
    )
    db_session.add(user)
    await db_session.commit()

    response = await client.post("/api/v1/auth/login", json={
        "email": "inactive@example.com",
        "password": "pass123",
    })
    assert response.status_code == 401
