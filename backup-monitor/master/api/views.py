import json
from fastapi import APIRouter, Request, Cookie, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import db
from auth.sessions import get_session_user

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# --- Jinja2 filters ---

def _os_badge(server) -> str:
    s = server if isinstance(server, dict) else dict(server)
    name = (s.get("os_name") or "").lower()
    ver = s.get("os_version") or ""
    label = f"{s.get('os_name','')} {ver}".strip() or "Unknown OS"
    if "ubuntu" in name and "22" in ver:
        css = "os-ubuntu22"
    elif "ubuntu" in name and "24" in ver:
        css = "os-ubuntu24"
    elif "ubuntu" in name:
        css = "os-ubuntu22"
    elif "debian" in name:
        css = "os-debian"
    elif "centos" in name:
        css = "os-centos"
    elif "alma" in name:
        css = "os-alma"
    elif "rocky" in name:
        css = "os-rocky"
    else:
        css = "os-unknown"
    return f'<span class="badge {css}">🐧 {label}</span>'

def _status_badge(obj) -> str:
    d = obj if isinstance(obj, dict) else dict(obj)
    status = d.get("last_backup_status") or d.get("status") or "stale"
    if status == "ok":
        return '<span class="badge badge-ok">✅ OK</span>'
    elif status == "failed":
        return '<span class="badge badge-failed">❌ FAILED</span>'
    else:
        return '<span class="badge badge-stale">⚠️ STALE</span>'

def _restore_badge(obj) -> str:
    d = obj if isinstance(obj, dict) else dict(obj)
    status = d.get("last_restore_status") or d.get("restore_status")
    if status == "ok":
        return '<span class="badge badge-ok">✅ OK</span>'
    elif status == "failed":
        return '<span class="badge badge-failed">❌ FAILED</span>'
    return '<span class="text-secondary">—</span>'

def _disk_bar(server) -> str:
    d = server if isinstance(server, dict) else dict(server)
    pct = d.get("disk_free_pct")
    if pct is None:
        return '<span class="text-secondary">—</span>'
    color = "green" if pct > 40 else ("yellow" if pct > 20 else "red")
    used = 100 - pct
    return (f'<div class="disk-bar">'
            f'<div class="disk-fill disk-fill-{color}" style="width:{used:.0f}%"></div>'
            f'</div>'
            f'<span class="text-secondary" style="font-size:0.8em">{pct:.0f}% libero</span>')

def _fromjson(val):
    if not val:
        return []
    try:
        return json.loads(val)
    except Exception:
        return []

templates.env.filters["os_badge"] = _os_badge
templates.env.filters["status_badge"] = _status_badge
templates.env.filters["restore_badge"] = _restore_badge
templates.env.filters["disk_bar"] = _disk_bar
templates.env.filters["fromjson"] = _fromjson

# --- Auth dependency ---

def _get_current_user(session: str | None) -> dict | None:
    if not session:
        return None
    return get_session_user(session)

# --- Routes ---

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse("login.html", {"request": request, "user": None, "error": error})

@router.post("/auth/login")
async def login_form(request: Request):
    import bcrypt
    from auth.sessions import create_session
    form = await request.form()
    username = form.get("username", "")
    password = form.get("password", "")
    totp_code = form.get("totp_code", "")
    with db.get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not user or not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return RedirectResponse("/login?error=Credenziali+non+valide", status_code=303)
    if user["totp_secret_enc"]:
        from auth.totp import verify_totp
        if not verify_totp(user["totp_secret_enc"], totp_code):
            return RedirectResponse("/login?error=Codice+2FA+non+valido", status_code=303)
    token = create_session(user["id"])
    resp = RedirectResponse("/", status_code=303)
    resp.set_cookie("session", token, httponly=True, samesite="strict", max_age=8*3600)
    return resp

@router.post("/auth/logout")
def logout_form(session: str | None = Cookie(default=None)):
    from auth.sessions import revoke_session
    if session:
        revoke_session(session)
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("session")
    return resp

@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: str | None = Cookie(default=None)):
    user = _get_current_user(session)
    if not user:
        return RedirectResponse("/login", status_code=303)
    with db.get_db() as conn:
        servers = conn.execute("""
            SELECT s.*,
                   br.status AS last_backup_status,
                   br.reported_at AS last_backup_at,
                   br.size_gb, br.disk_free_pct,
                   rr.status AS last_restore_status
            FROM servers s
            LEFT JOIN backup_runs br ON br.id = (
                SELECT id FROM backup_runs WHERE vps_id=s.vps_id ORDER BY id DESC LIMIT 1)
            LEFT JOIN restore_runs rr ON rr.id = (
                SELECT id FROM restore_runs WHERE vps_id=s.vps_id ORDER BY id DESC LIMIT 1)
            ORDER BY s.vps_id
        """).fetchall()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "servers": [dict(s) for s in servers],
    })

@router.post("/servers/{vps_id}/edit")
async def edit_server_form(vps_id: str, request: Request, session: str | None = Cookie(default=None)):
    user = _get_current_user(session)
    if not user:
        return RedirectResponse("/login", status_code=303)
    form = await request.form()
    # Parse folders: one per line, strip whitespace, remove empty lines
    folders_raw = form.get("folders", "")
    folders = [f.strip() for f in folders_raw.splitlines() if f.strip()]
    hostname = form.get("hostname", "").strip()
    cliente = form.get("cliente", "").strip()
    backup_hour = form.get("backup_hour", "2").strip()
    try:
        backup_hour_int = int(backup_hour)
    except ValueError:
        backup_hour_int = 2
    import json as _json
    with db.get_db() as conn:
        updates = {}
        if hostname: updates["hostname"] = hostname
        if cliente: updates["cliente"] = cliente
        if folders: updates["folders"] = _json.dumps(folders)
        updates["backup_hour"] = backup_hour_int
        if updates:
            set_clause = ", ".join(f"{k}=?" for k in updates)
            conn.execute(f"UPDATE servers SET {set_clause} WHERE vps_id=?",
                         list(updates.values()) + [vps_id])
    return RedirectResponse(f"/servers/{vps_id}?saved=1", status_code=303)

@router.get("/servers/{vps_id}", response_class=HTMLResponse)
def server_detail(vps_id: str, request: Request, session: str | None = Cookie(default=None)):
    user = _get_current_user(session)
    if not user:
        return RedirectResponse("/login", status_code=303)
    with db.get_db() as conn:
        server = conn.execute("SELECT * FROM servers WHERE vps_id=?", (vps_id,)).fetchone()
        if not server:
            raise HTTPException(status_code=404, detail="VPS non trovata")
        runs = conn.execute("""
            SELECT br.*, rr.status AS restore_status, rr.checksum_ok
            FROM backup_runs br
            LEFT JOIN restore_runs rr ON rr.backup_run_id = br.id
            WHERE br.vps_id=? ORDER BY br.id DESC LIMIT 14
        """, (vps_id,)).fetchall()
    return templates.TemplateResponse("detail.html", {
        "request": request,
        "user": user,
        "server": dict(server),
        "runs": [dict(r) for r in runs],
    })
