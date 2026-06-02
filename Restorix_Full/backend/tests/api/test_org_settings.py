import pytest
import uuid
from sqlalchemy import select
from app.models.organization import Organization, OrgPlan
from app.models.user import User, UserRole
from app.core.security import hash_password, create_access_token


@pytest.fixture
async def admin_client(client, db_session):
    """Create org + admin user and inject access_token cookie."""
    org = Organization(
        id=uuid.uuid4(),
        name=f"TestOrg-{uuid.uuid4().hex[:8]}",
        plan=OrgPlan.saas_starter,
        require_2fa=False,
    )
    db_session.add(org)
    await db_session.flush()

    user = User(
        id=uuid.uuid4(),
        org_id=org.id,
        email=f"admin-{uuid.uuid4().hex[:8]}@test.local",
        password_hash=hash_password("Test1234!"),
        role=UserRole.admin,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    token = create_access_token(subject=str(user.id), role=user.role.value)
    client.cookies.set("access_token", token)
    yield client


@pytest.mark.asyncio
async def test_update_settings_valid_cron_and_retention(admin_client):
    r = await admin_client.patch(
        "/api/v1/organizations/me/settings",
        json={"schedule_cleanup_cron": "0 4 * * *", "audit_retention_days": 180},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["schedule_cleanup_cron"] == "0 4 * * *"
    assert body["audit_retention_days"] == 180


@pytest.mark.asyncio
async def test_invalid_cron_rejected(admin_client):
    r = await admin_client.patch(
        "/api/v1/organizations/me/settings",
        json={"schedule_cleanup_cron": "not a cron"},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_audit_retention_below_min_rejected(admin_client):
    r = await admin_client.patch(
        "/api/v1/organizations/me/settings",
        json={"audit_retention_days": 30},
    )
    assert r.status_code == 422
