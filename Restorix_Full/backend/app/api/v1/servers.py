import logging
import uuid
import secrets
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.server import Server
from app.models.db_instance import DbInstance
from app.models.user import User
from app.schemas.server import ServerCreate, ServerOut, DbInstanceCreate, DbInstanceOut
from app.api.deps import get_current_user
from app.core.encryption import encrypt, decrypt
from app.services.audit import log_event, EventType
import json

_logger = logging.getLogger(__name__)

router = APIRouter()


async def _safe_audit(db, **kwargs):
    """Best-effort audit log. Never raises — failures only warn."""
    try:
        await log_event(db, **kwargs)
        await db.commit()
    except Exception as audit_exc:
        _logger.warning("audit log failed: %s", audit_exc)


def _get_org_id(current_user: User) -> uuid.UUID:
    return current_user.org_id


# ── Servers ──────────────────────────────────────────────

@router.get("/", response_model=list[ServerOut])
async def list_servers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Server)
        .where(Server.org_id == _get_org_id(current_user), Server.is_active == True)
        .order_by(Server.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=ServerOut, status_code=status.HTTP_201_CREATED)
async def create_server(
    payload: ServerCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("superadmin", "admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    engine = payload.engine if payload.engine in ("mssql", "mysql") else "mssql"
    server = Server(
        org_id=_get_org_id(current_user),
        name=payload.name,
        hostname=payload.hostname,
        engine=engine,
        agent_token=secrets.token_hex(32),
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)

    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.SERVER_CREATED,
        target_type="server", target_id=str(server.id),
        description=f"Created server {server.name} ({server.hostname})",
        metadata={"name": server.name, "hostname": server.hostname},
        request=request,
    )

    return server


@router.get("/{server_id}", response_model=ServerOut)
async def get_server(
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Server).where(
            Server.id == server_id,
            Server.org_id == _get_org_id(current_user),
            Server.is_active == True,
        )
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    return server


from pydantic import BaseModel as _BaseModel


class ServerUpdate(_BaseModel):
    name: str | None = None
    hostname: str | None = None
    engine: str | None = None


@router.patch("/{server_id}", response_model=ServerOut)
async def update_server(
    server_id: uuid.UUID,
    payload: ServerUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("superadmin", "admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    srv = await db.get(Server, server_id)
    if not srv or srv.org_id != _get_org_id(current_user) or not srv.is_active:
        raise HTTPException(status_code=404, detail="Server not found")
    changed = []
    if payload.name is not None:
        srv.name = payload.name
        changed.append("name")
    if payload.hostname is not None:
        srv.hostname = payload.hostname
        changed.append("hostname")
    if payload.engine is not None and payload.engine in ("mssql", "mysql"):
        srv.engine = payload.engine
        changed.append("engine")
    db.add(srv)
    await db.commit()
    await db.refresh(srv)

    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.SERVER_UPDATED,
        target_type="server", target_id=str(srv.id),
        description=f"Updated server {srv.name}",
        metadata={"name": srv.name, "fields_changed": changed},
        request=request,
    )

    return srv


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(
    server_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await db.execute(
        select(Server).where(
            Server.id == server_id,
            Server.org_id == _get_org_id(current_user),
        )
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    server.is_active = False
    db.add(server)
    await db.commit()

    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.SERVER_DELETED,
        target_type="server", target_id=str(server.id),
        description=f"Deleted server {server.name}",
        metadata={"name": server.name, "hostname": server.hostname},
        request=request,
    )


@router.post("/{server_id}/rotate-token", response_model=ServerOut)
async def rotate_token(
    server_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await db.execute(
        select(Server).where(
            Server.id == server_id,
            Server.org_id == _get_org_id(current_user),
            Server.is_active == True,
        )
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    server.agent_token = secrets.token_hex(32)
    db.add(server)
    await db.commit()
    await db.refresh(server)

    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.SERVER_AGENT_TOKEN_REGENERATED,
        target_type="server", target_id=str(server.id),
        description=f"Rotated agent token for server {server.name}",
        metadata={"name": server.name},
        request=request,
    )

    return server


@router.post("/{server_id}/request-update", response_model=ServerOut)
async def request_agent_update(
    server_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Flag the server's agent for update. The agent's root updater (systemd timer)
    picks this up within ~10 minutes and self-updates."""
    if current_user.role not in ("superadmin", "admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    result = await db.execute(
        select(Server).where(
            Server.id == server_id,
            Server.org_id == _get_org_id(current_user),
            Server.is_active == True,
        )
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    server.update_requested = True
    server.update_status = "updating"
    db.add(server)
    await db.commit()
    await db.refresh(server)

    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.SERVER_UPDATED,
        target_type="server", target_id=str(server.id),
        description=f"Requested agent update for server {server.name}",
        metadata={"name": server.name},
        request=request,
    )
    return server


class AutoUpdatePayload(_BaseModel):
    enabled: bool


@router.patch("/{server_id}/auto-update", response_model=ServerOut)
async def set_auto_update(
    server_id: uuid.UUID,
    payload: AutoUpdatePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle automatic agent updates for a server."""
    if current_user.role not in ("superadmin", "admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    result = await db.execute(
        select(Server).where(
            Server.id == server_id,
            Server.org_id == _get_org_id(current_user),
            Server.is_active == True,
        )
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    server.auto_update_enabled = payload.enabled
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return server


# ── Remote agent management commands ──────────────────────
from app.models.agent_command import AgentCommand, AGENT_ACTIONS


class AgentCommandIn(_BaseModel):
    action: str
    params: dict | None = None


class AgentCommandOut(_BaseModel):
    id: uuid.UUID
    action: str
    params: dict | None = None
    status: str
    result: str | None = None
    created_at: object | None = None
    finished_at: object | None = None

    model_config = {"from_attributes": True}


@router.post("/{server_id}/commands", response_model=AgentCommandOut, status_code=201)
async def enqueue_command(
    server_id: uuid.UUID,
    payload: AgentCommandIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Queue a whitelisted management command for the server's agent."""
    if current_user.role not in ("superadmin", "admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    if payload.action not in AGENT_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Unknown action: {payload.action}")
    result = await db.execute(
        select(Server).where(
            Server.id == server_id,
            Server.org_id == _get_org_id(current_user),
            Server.is_active == True,
        )
    )
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    # Validate set_config params server-side
    params = payload.params or {}
    if payload.action == "set_config":
        clean: dict = {}
        if "poll_interval_seconds" in params:
            try:
                v = int(params["poll_interval_seconds"])
            except (TypeError, ValueError):
                raise HTTPException(status_code=400, detail="poll_interval_seconds must be an integer")
            if not (10 <= v <= 3600):
                raise HTTPException(status_code=400, detail="poll_interval_seconds must be 10..3600")
            clean["poll_interval_seconds"] = v
        if "log_level" in params:
            lvl = str(params["log_level"]).upper()
            if lvl not in ("DEBUG", "INFO", "WARNING", "ERROR"):
                raise HTTPException(status_code=400, detail="invalid log_level")
            clean["log_level"] = lvl
        if "temp_dir" in params:
            td = str(params["temp_dir"])
            if not td.startswith("/") or ".." in td:
                raise HTTPException(status_code=400, detail="temp_dir must be an absolute path without '..'")
            clean["temp_dir"] = td
        if not clean:
            raise HTTPException(status_code=400, detail="no valid config fields provided")
        params = clean

    cmd = AgentCommand(
        server_id=server.id,
        action=payload.action,
        params=params or None,
        created_by_user_id=current_user.id,
    )
    db.add(cmd)
    await db.commit()
    await db.refresh(cmd)

    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.SERVER_UPDATED,
        target_type="server", target_id=str(server.id),
        description=f"Queued agent command '{payload.action}' for {server.name}",
        metadata={"action": payload.action},
        request=request,
    )
    return cmd


@router.get("/{server_id}/commands", response_model=list[AgentCommandOut])
async def list_commands(
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Recent management commands for a server's agent (newest first)."""
    srv = await db.get(Server, server_id)
    if not srv or srv.org_id != _get_org_id(current_user) or not srv.is_active:
        raise HTTPException(status_code=404, detail="Server not found")
    result = await db.execute(
        select(AgentCommand)
        .where(AgentCommand.server_id == server_id)
        .order_by(AgentCommand.created_at.desc())
        .limit(20)
    )
    return result.scalars().all()


# ── DbInstances ───────────────────────────────────────────

@router.get("/{server_id}/databases", response_model=list[DbInstanceOut])
async def list_databases(
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    srv = await db.get(Server, server_id)
    if not srv or srv.org_id != _get_org_id(current_user) or not srv.is_active:
        raise HTTPException(status_code=404, detail="Server not found")

    result = await db.execute(
        select(DbInstance).where(
            DbInstance.server_id == server_id,
            DbInstance.is_active == True,
        )
    )
    return result.scalars().all()


@router.post("/{server_id}/databases", response_model=DbInstanceOut, status_code=201)
async def create_database(
    server_id: uuid.UUID,
    payload: DbInstanceCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("superadmin", "admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    srv = await db.get(Server, server_id)
    if not srv or srv.org_id != _get_org_id(current_user) or not srv.is_active:
        raise HTTPException(status_code=404, detail="Server not found")

    credentials = None
    if payload.username or payload.password:
        credentials = encrypt(json.dumps({
            "username": payload.username or "",
            "password": payload.password or "",
        }))

    dbi = DbInstance(
        server_id=server_id,
        name=payload.name,
        connection_string=payload.connection_string,
        credentials_enc=credentials,
    )
    db.add(dbi)
    await db.commit()
    await db.refresh(dbi)

    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.DBINSTANCE_CREATED,
        target_type="db_instance", target_id=str(dbi.id),
        description=f"Created DB instance {dbi.name} on server {srv.name}",
        metadata={"name": dbi.name, "server_id": str(server_id)},
        request=request,
    )

    return dbi


class DbInstanceUpdate(_BaseModel):
    name: str | None = None
    connection_string: str | None = None
    username: str | None = None
    password: str | None = None


@router.patch("/{server_id}/databases/{db_id}", response_model=DbInstanceOut)
async def update_database(
    server_id: uuid.UUID,
    db_id: uuid.UUID,
    payload: DbInstanceUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("superadmin", "admin", "operator"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    srv = await db.get(Server, server_id)
    if not srv or srv.org_id != _get_org_id(current_user):
        raise HTTPException(status_code=404, detail="Server not found")
    dbi = await db.get(DbInstance, db_id)
    if not dbi or dbi.server_id != server_id:
        raise HTTPException(status_code=404, detail="Database not found")
    if payload.name is not None:
        dbi.name = payload.name
    if payload.connection_string is not None:
        dbi.connection_string = payload.connection_string
    if payload.username is not None or payload.password is not None:
        existing = {}
        if dbi.credentials_enc:
            try:
                existing = json.loads(decrypt(dbi.credentials_enc))
            except Exception:
                pass
        new_user = payload.username if payload.username is not None else existing.get("username", "")
        new_pass = payload.password if payload.password is not None else existing.get("password", "")
        dbi.credentials_enc = encrypt(json.dumps({"username": new_user, "password": new_pass}))
    db.add(dbi)
    await db.commit()
    await db.refresh(dbi)

    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.DBINSTANCE_UPDATED,
        target_type="db_instance", target_id=str(dbi.id),
        description=f"Updated DB instance {dbi.name}",
        metadata={"name": dbi.name, "server_id": str(server_id)},
        request=request,
    )

    return dbi


@router.delete("/{server_id}/databases/{db_id}", status_code=204)
async def delete_database(
    server_id: uuid.UUID,
    db_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ("superadmin", "admin"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    srv = await db.get(Server, server_id)
    if not srv or srv.org_id != _get_org_id(current_user):
        raise HTTPException(status_code=404, detail="Server not found")

    dbi = await db.get(DbInstance, db_id)
    if not dbi or dbi.server_id != server_id:
        raise HTTPException(status_code=404, detail="Database not found")

    dbi.is_active = False
    db.add(dbi)
    await db.commit()

    await _safe_audit(
        db,
        org_id=current_user.org_id, user_id=current_user.id,
        event_type=EventType.DBINSTANCE_DELETED,
        target_type="db_instance", target_id=str(dbi.id),
        description=f"Deleted DB instance {dbi.name}",
        metadata={"name": dbi.name, "server_id": str(server_id)},
        request=request,
    )


# ── Discovery ─────────────────────────────────────────────
from pydantic import BaseModel
from app.services import discovery


class DiscoverRequest(BaseModel):
    connection_string: str
    username: str | None = ""
    password: str | None = ""


@router.post("/{server_id}/discover")
async def start_discovery(
    server_id: uuid.UUID,
    payload: DiscoverRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    srv = await db.get(Server, server_id)
    if not srv or srv.org_id != _get_org_id(current_user) or not srv.is_active:
        raise HTTPException(status_code=404, detail="Server not found")
    await discovery.store_request(
        server_id,
        payload.connection_string,
        payload.username or "",
        payload.password or "",
        engine=srv.engine if srv.engine else "mssql",
    )
    return {"status": "queued"}


@router.get("/{server_id}/discovery")
async def get_discovery_result(
    server_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    srv = await db.get(Server, server_id)
    if not srv or srv.org_id != _get_org_id(current_user):
        raise HTTPException(status_code=404, detail="Server not found")

    result = await discovery.get_result(server_id)
    if result is not None:
        return {"status": "ready", **result}

    req = await discovery.get_request_for_agent(server_id)
    if req is not None:
        return {"status": "pending"}

    return {"status": "none"}
