from fastapi import APIRouter
from app.api.v1 import auth, users, servers, storage, jobs, runs, agent, notifications, organizations, audit, restore_hub

router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(servers.router, prefix="/servers", tags=["servers"])
router.include_router(storage.router, prefix="/storage", tags=["storage"])
router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
router.include_router(runs.router, prefix="/runs", tags=["runs"])
router.include_router(agent.router, prefix="/agent", tags=["agent"])
router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
router.include_router(audit.router, prefix="/audit", tags=["audit"])
router.include_router(restore_hub.router, prefix="/restore-hub", tags=["restore-hub"])
