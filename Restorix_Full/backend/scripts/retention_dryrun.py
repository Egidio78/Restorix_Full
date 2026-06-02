"""CLI for retention dry-run.

Usage:
    docker compose exec api python -m scripts.retention_dryrun --org-id <uuid>
    docker compose exec api python -m scripts.retention_dryrun --all
"""
import argparse
import asyncio
import json
from uuid import UUID

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.organization import Organization
from app.services.retention import RetentionService


async def run_for_org(org_id: UUID) -> None:
    async with AsyncSessionLocal() as db:
        service = RetentionService(db)
        report = await service.purge_org(org_id, dry_run=True)
        print(json.dumps({
            "org_id": report.org_id,
            "candidates": report.candidates,
            "items": report.items,
        }, indent=2, default=str))


async def run_for_all() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Organization))
        orgs = result.scalars().all()
    for org in orgs:
        print(f"\n=== Org {org.id} ({org.name}) ===")
        await run_for_org(org.id)


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--org-id", help="UUID of the organization")
    group.add_argument("--all", action="store_true", help="Run for all orgs")
    args = parser.parse_args()

    if args.all:
        asyncio.run(run_for_all())
    else:
        asyncio.run(run_for_org(UUID(args.org_id)))


if __name__ == "__main__":
    main()
