"""
Seed script: create the initial superadmin user.

Usage (inside the Docker container or with correct DB env):
    python scripts/create_admin.py

Or via Docker:
    docker compose exec api python scripts/create_admin.py
"""
import asyncio
import os
import sys

# Ensure app module is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import AsyncSessionLocal
from app.models.organization import Organization, OrgPlan
from app.models.user import User, UserRole
from app.core.security import hash_password


async def create_admin() -> None:
    email = os.environ.get("ADMIN_EMAIL", "admin@edminformatica.com")
    password = os.environ.get("ADMIN_PASSWORD", "Admin123!")
    org_name = os.environ.get("ADMIN_ORG", "EDM Informatica")

    async with AsyncSessionLocal() as db:
        org = Organization(name=org_name, plan=OrgPlan.saas_enterprise)
        db.add(org)
        await db.flush()

        user = User(
            org_id=org.id,
            email=email,
            password_hash=hash_password(password),
            role=UserRole.superadmin,
        )
        db.add(user)
        await db.commit()

        print(f"✓ Organizzazione creata: {org_name}")
        print(f"✓ Utente superadmin creato: {email}")
        print(f"  Password: {password}")
        print()
        print("IMPORTANTE: Cambia la password al primo accesso!")


if __name__ == "__main__":
    asyncio.run(create_admin())
