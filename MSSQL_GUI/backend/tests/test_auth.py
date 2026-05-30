import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.organization import Organization, OrgPlan
from app.models.user import User, UserRole
from app.core.security import hash_password


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
