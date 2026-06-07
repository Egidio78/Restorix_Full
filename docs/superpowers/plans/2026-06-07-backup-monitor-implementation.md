# Backup Monitor — Piano di Implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Costruire un sistema completo di backup per ~100 VPS TeamSystem/AcuCOBOL con storage S3 Contabo, restore test automatico, dashboard web centralizzata e notifiche multicanale.

**Architecture:** Ogni VPS esegue script bash (cron 02:00 backup + 03:30 restore test) che inviano risultati via HTTP al Master Service. Il Master Service (FastAPI + SQLite) espone dashboard web con auth 2FA/passkey, alert engine e download streaming da S3.

**Tech Stack:** Python 3.12, FastAPI, SQLite, Jinja2, restic, Ansible, pyotp, py_webauthn, PyJWT, httpx, bcrypt, pytest

---

## Struttura File

```
backup-monitor/
├── master/
│   ├── main.py                 # FastAPI app, lifespan, middleware, routers
│   ├── db.py                   # sqlite3 init, get_db(), schema DDL
│   ├── config.py               # Settings da env vars (MASTER_SECRET, SMTP_*, ecc.)
│   ├── api/
│   │   ├── __init__.py
│   │   ├── backup.py           # POST /api/v1/backup/report
│   │   ├── restore.py          # POST /api/v1/restore/report
│   │   ├── servers.py          # GET /api/v1/servers, /api/v1/servers/{id}
│   │   ├── download.py         # GET download streaming + JWT link
│   │   └── auth.py             # login, logout, totp-setup, webauthn endpoints
│   ├── auth/
│   │   ├── __init__.py
│   │   ├── totp.py             # generate_secret(), verify_totp(), make_recovery_codes()
│   │   ├── webauthn.py         # generate_challenge(), verify_registration(), verify_auth()
│   │   └── sessions.py         # create_session(), validate_session(), revoke_session()
│   ├── alerts/
│   │   ├── __init__.py
│   │   ├── engine.py           # run_checks(): stale >25h, failed, restore fallito
│   │   ├── telegram.py         # send_telegram(msg: str)
│   │   ├── email_notify.py     # send_alert_email(), send_daily_digest()
│   │   └── whatsapp.py         # send_whatsapp(msg: str) via Callmebot
│   ├── templates/
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── setup_2fa.html
│   │   ├── dashboard.html
│   │   └── server_detail.html
│   ├── static/style.css
│   ├── manage.py               # CLI: python manage.py create-user --username admin
│   ├── requirements.txt
│   └── tests/
│       ├── conftest.py
│       ├── test_db.py
│       ├── test_api_backup.py
│       ├── test_api_restore.py
│       ├── test_api_servers.py
│       ├── test_auth_totp.py
│       ├── test_auth_sessions.py
│       ├── test_alerts.py
│       └── test_download.py
├── vps/
│   ├── backup-teamsystem.sh
│   └── restore-test-teamsystem.sh
└── ansible/
    ├── inventory.yml
    ├── playbook.yml
    └── roles/backup-agent/
        ├── tasks/main.yml
        ├── defaults/main.yml
        └── templates/
            ├── backup.sh.j2
            ├── restore_test.sh.j2
            └── restic.env.j2
```

---

## Task 1: Scaffold + DB Schema

**Files:**
- Create: `backup-monitor/master/db.py`
- Create: `backup-monitor/master/config.py`
- Create: `backup-monitor/master/requirements.txt`
- Create: `backup-monitor/master/tests/conftest.py`
- Create: `backup-monitor/master/tests/test_db.py`

- [ ] **Step 1: Crea struttura directory**

```bash
mkdir -p backup-monitor/master/{api,auth,alerts,templates,static,tests}
touch backup-monitor/master/api/__init__.py
touch backup-monitor/master/auth/__init__.py
touch backup-monitor/master/alerts/__init__.py
touch backup-monitor/master/tests/__init__.py
```

- [ ] **Step 2: Scrivi `requirements.txt`**

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
jinja2==3.1.4
python-multipart==0.0.9
bcrypt==4.2.0
pyotp==2.9.0
qrcode[pil]==7.4.2
py_webauthn==2.1.0
PyJWT==2.9.0
httpx==0.27.2
cryptography==43.0.1
pytest==8.3.3
pytest-asyncio==0.24.0
anyio==4.6.0
```

- [ ] **Step 3: Scrivi `config.py`**

```python
import os

MASTER_SECRET = os.environ["MASTER_SECRET"]          # segreto HMAC per API key VPS
JWT_SECRET = os.environ["JWT_SECRET"]                # segreto JWT download link
TOTP_ENCRYPTION_KEY = os.environ["TOTP_ENCRYPTION_KEY"]  # Fernet key per cifrare totp_secret
DB_PATH = os.environ.get("DB_PATH", "backup_monitor.db")
MASTER_BASE_URL = os.environ.get("MASTER_BASE_URL", "http://localhost:8080")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
ALERT_EMAIL_TO = os.environ.get("ALERT_EMAIL_TO", "")

CALLMEBOT_PHONE = os.environ.get("CALLMEBOT_PHONE", "")
CALLMEBOT_APIKEY = os.environ.get("CALLMEBOT_APIKEY", "")

STALE_HOURS = int(os.environ.get("STALE_HOURS", "25"))
LARGE_FILE_THRESHOLD_GB = float(os.environ.get("LARGE_FILE_THRESHOLD_GB", "5.0"))
```

- [ ] **Step 4: Scrivi `db.py`**

```python
import sqlite3
import config

DDL = """
CREATE TABLE IF NOT EXISTS servers (
    vps_id      TEXT PRIMARY KEY,
    hostname    TEXT NOT NULL,
    cliente     TEXT NOT NULL DEFAULT '',
    os_name     TEXT NOT NULL DEFAULT '',
    os_version  TEXT NOT NULL DEFAULT '',
    folders     TEXT NOT NULL DEFAULT '',   -- JSON array di path
    backup_hour INTEGER NOT NULL DEFAULT 2,
    api_key     TEXT NOT NULL,              -- SHA256(MASTER_SECRET + vps_id)
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS backup_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    vps_id      TEXT NOT NULL REFERENCES servers(vps_id),
    status      TEXT NOT NULL,              -- 'ok' | 'failed'
    snapshot_id TEXT,
    size_gb     REAL,
    duration_s  INTEGER,
    downtime_s  INTEGER,
    error_msg   TEXT,
    folders     TEXT,                       -- JSON array (path backuppati in questa run)
    disk_free_pct REAL,
    reported_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS restore_runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    vps_id       TEXT NOT NULL REFERENCES servers(vps_id),
    backup_run_id INTEGER REFERENCES backup_runs(id),
    status       TEXT NOT NULL,             -- 'ok' | 'failed'
    checksum_ok  INTEGER,                   -- 1 | 0
    duration_s   INTEGER,
    error_msg    TEXT,
    reported_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS users (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    username         TEXT NOT NULL UNIQUE,
    password_hash    TEXT NOT NULL,
    totp_secret_enc  TEXT,                  -- Fernet-encrypted, NULL se non ancora configurato
    recovery_codes   TEXT,                  -- JSON array di codici hash
    passkey_creds    TEXT NOT NULL DEFAULT '[]',  -- JSON array WebAuthn credentials
    role             TEXT NOT NULL DEFAULT 'admin',  -- 'admin' | 'readonly'
    created_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    token       TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    expires_at  TEXT NOT NULL,
    revoked     INTEGER NOT NULL DEFAULT 0
);
"""

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    with get_db() as conn:
        conn.executescript(DDL)
```

- [ ] **Step 5: Scrivi il test**

```python
# tests/test_db.py
import os, pytest
os.environ.setdefault("MASTER_SECRET", "testsecret")
os.environ.setdefault("JWT_SECRET", "testjwt")
os.environ.setdefault("TOTP_ENCRYPTION_KEY", "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ=")

import db

def test_init_db_creates_tables(tmp_path):
    import config
    config.DB_PATH = str(tmp_path / "test.db")
    db.init_db()
    conn = db.get_db()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"servers", "backup_runs", "restore_runs", "users", "sessions"} <= tables
```

- [ ] **Step 6: Scrivi `tests/conftest.py`**

```python
import os, pytest
os.environ.setdefault("MASTER_SECRET", "testsecret")
os.environ.setdefault("JWT_SECRET", "testjwt")
os.environ.setdefault("TOTP_ENCRYPTION_KEY", "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXQ=")
os.environ.setdefault("DB_PATH", ":memory:")

import db

@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
```

- [ ] **Step 7: Installa dipendenze e lancia test**

```bash
cd backup-monitor/master
pip install -r requirements.txt
pytest tests/test_db.py -v
```
Atteso: `PASSED`

- [ ] **Step 8: Commit**

```bash
git add backup-monitor/
git commit -m "feat: scaffold backup-monitor with db schema (5 tables)"
```

---

## Task 2: Script Bash Backup (VPS-side)

**Files:**
- Create: `backup-monitor/vps/backup-teamsystem.sh`

- [ ] **Step 1: Scrivi lo script**

```bash
#!/usr/bin/env bash
# backup-teamsystem.sh — eseguito da cron alle 02:00 su ogni VPS
# Variabili d'ambiente lette da /etc/restic/restic.env

set -euo pipefail

ENV_FILE="/etc/restic/restic.env"
[[ -f "$ENV_FILE" ]] || { echo "ERRORE: $ENV_FILE non trovato"; exit 1; }
# shellcheck source=/dev/null
source "$ENV_FILE"

# Variabili richieste in restic.env:
# RESTIC_REPOSITORY, RESTIC_PASSWORD, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
# MASTER_URL, VPS_ID, API_KEY, TEAMSYSTEM_SERVICE, BACKUP_FOLDERS (spazio-separati)

MASTER_URL="${MASTER_URL:?}"
VPS_ID="${VPS_ID:?}"
API_KEY="${API_KEY:?}"
TEAMSYSTEM_SERVICE="${TEAMSYSTEM_SERVICE:-teamsystem}"
BACKUP_FOLDERS="${BACKUP_FOLDERS:-/home/Nativo}"

START_TS=$(date +%s)
STOP_TS=$START_TS
STATUS="failed"
SNAPSHOT_ID=""
SIZE_GB="0"
ERROR_MSG=""

# Ferma il servizio
systemctl stop "$TEAMSYSTEM_SERVICE" || true
STOP_TS=$(date +%s)

# Esegui backup
BACKUP_JSON=$(restic backup $BACKUP_FOLDERS --json 2>/dev/null | tail -1) || {
    ERROR_MSG="restic backup fallito"
}

# Riavvia il servizio
systemctl start "$TEAMSYSTEM_SERVICE" || true

END_TS=$(date +%s)
DOWNTIME_S=$((END_TS - STOP_TS))
DURATION_S=$((END_TS - START_TS))

if [[ -n "$BACKUP_JSON" && -z "$ERROR_MSG" ]]; then
    STATUS="ok"
    SNAPSHOT_ID=$(echo "$BACKUP_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('snapshot_id',''))" 2>/dev/null || echo "")
    SIZE_BYTES=$(echo "$BACKUP_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total_bytes_processed',0))" 2>/dev/null || echo "0")
    SIZE_GB=$(echo "scale=2; $SIZE_BYTES/1073741824" | bc)
fi

# Spazio disco libero
DISK_FREE_PCT=$(df /home --output=pcent | tail -1 | tr -d ' %')
DISK_FREE_PCT=$((100 - DISK_FREE_PCT))

# Cartelle come JSON array
FOLDERS_JSON=$(echo "$BACKUP_FOLDERS" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().split()))")

# Applica retention
restic forget --keep-daily 7 --keep-weekly 4 --prune --quiet || true

# Invia report al Master
curl -sf -X POST "$MASTER_URL/api/v1/backup/report" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d "{
        \"vps_id\": \"$VPS_ID\",
        \"status\": \"$STATUS\",
        \"snapshot_id\": \"$SNAPSHOT_ID\",
        \"size_gb\": $SIZE_GB,
        \"duration_s\": $DURATION_S,
        \"downtime_s\": $DOWNTIME_S,
        \"error_msg\": \"$ERROR_MSG\",
        \"folders\": $FOLDERS_JSON,
        \"disk_free_pct\": $DISK_FREE_PCT
    }" || echo "WARN: impossibile inviare report al Master"

exit 0
```

- [ ] **Step 2: Rendi eseguibile e verifica sintassi**

```bash
chmod +x backup-monitor/vps/backup-teamsystem.sh
bash -n backup-monitor/vps/backup-teamsystem.sh
```
Atteso: nessun output (sintassi OK)

- [ ] **Step 3: Commit**

```bash
git add backup-monitor/vps/backup-teamsystem.sh
git commit -m "feat: vps backup script with restic + report to master"
```

---

## Task 3: Script Bash Restore Test (VPS-side)

**Files:**
- Create: `backup-monitor/vps/restore-test-teamsystem.sh`

- [ ] **Step 1: Scrivi lo script**

```bash
#!/usr/bin/env bash
# restore-test-teamsystem.sh — eseguito da cron alle 03:30 su ogni VPS

set -euo pipefail

ENV_FILE="/etc/restic/restic.env"
source "$ENV_FILE"

MASTER_URL="${MASTER_URL:?}"
VPS_ID="${VPS_ID:?}"
API_KEY="${API_KEY:?}"
BACKUP_FOLDERS="${BACKUP_FOLDERS:-/home/Nativo}"
RESTORE_TMP="/tmp/restic-restore-test-$$"

STATUS="failed"
CHECKSUM_OK=0
DURATION_S=0
ERROR_MSG=""
START_TS=$(date +%s)

cleanup() { rm -rf "$RESTORE_TMP"; }
trap cleanup EXIT

# Recupera snapshot_id dell'ultimo backup riuscito
SNAPSHOT_ID=$(curl -sf "$MASTER_URL/api/v1/servers/$VPS_ID/latest-snapshot" \
    -H "X-API-Key: $API_KEY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('snapshot_id',''))" 2>/dev/null || echo "")

if [[ -z "$SNAPSHOT_ID" ]]; then
    ERROR_MSG="nessun snapshot disponibile"
else
    # File campione: il più recentemente modificato nella prima cartella
    FIRST_FOLDER=$(echo "$BACKUP_FOLDERS" | awk '{print $1}')
    SAMPLE_FILE=$(find "$FIRST_FOLDER" -type f -printf '%T@ %p\n' 2>/dev/null \
        | sort -rn | head -1 | awk '{print $2}')

    if [[ -z "$SAMPLE_FILE" ]]; then
        ERROR_MSG="nessun file trovato in $FIRST_FOLDER"
    else
        ORIG_CHECKSUM=$(sha256sum "$SAMPLE_FILE" | awk '{print $1}')
        RELATIVE_PATH="${SAMPLE_FILE#/}"

        mkdir -p "$RESTORE_TMP"
        restic restore "$SNAPSHOT_ID" \
            --target "$RESTORE_TMP" \
            --include "/$RELATIVE_PATH" --quiet 2>/dev/null || {
            ERROR_MSG="restic restore fallito"
        }

        if [[ -z "$ERROR_MSG" ]]; then
            RESTORED_FILE="$RESTORE_TMP/$RELATIVE_PATH"
            if [[ -f "$RESTORED_FILE" ]]; then
                RESTORED_CHECKSUM=$(sha256sum "$RESTORED_FILE" | awk '{print $1}')
                if [[ "$ORIG_CHECKSUM" == "$RESTORED_CHECKSUM" ]]; then
                    STATUS="ok"
                    CHECKSUM_OK=1
                else
                    ERROR_MSG="checksum mismatch: orig=$ORIG_CHECKSUM restored=$RESTORED_CHECKSUM"
                fi
            else
                ERROR_MSG="file ripristinato non trovato: $RESTORED_FILE"
            fi
        fi
    fi
fi

END_TS=$(date +%s)
DURATION_S=$((END_TS - START_TS))

curl -sf -X POST "$MASTER_URL/api/v1/restore/report" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d "{
        \"vps_id\": \"$VPS_ID\",
        \"status\": \"$STATUS\",
        \"checksum_ok\": $CHECKSUM_OK,
        \"duration_s\": $DURATION_S,
        \"error_msg\": \"$ERROR_MSG\"
    }" || echo "WARN: impossibile inviare report restore al Master"

exit 0
```

- [ ] **Step 2: Verifica sintassi**

```bash
chmod +x backup-monitor/vps/restore-test-teamsystem.sh
bash -n backup-monitor/vps/restore-test-teamsystem.sh
```

- [ ] **Step 3: Commit**

```bash
git add backup-monitor/vps/restore-test-teamsystem.sh
git commit -m "feat: vps restore test script with sha256 checksum verification"
```

---

## Task 4: API — Backup Report + Restore Report

**Files:**
- Create: `backup-monitor/master/api/backup.py`
- Create: `backup-monitor/master/api/restore.py`
- Create: `backup-monitor/master/tests/test_api_backup.py`
- Create: `backup-monitor/master/tests/test_api_restore.py`

- [ ] **Step 1: Scrivi `api/backup.py`**

```python
import hashlib, json
from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional
import db, config

router = APIRouter()

class BackupReport(BaseModel):
    vps_id: str
    status: str          # 'ok' | 'failed'
    snapshot_id: Optional[str] = None
    size_gb: Optional[float] = None
    duration_s: Optional[int] = None
    downtime_s: Optional[int] = None
    error_msg: Optional[str] = None
    folders: Optional[list[str]] = None
    disk_free_pct: Optional[float] = None

def _verify_api_key(vps_id: str, api_key: str):
    expected = hashlib.sha256(f"{config.MASTER_SECRET}{vps_id}".encode()).hexdigest()
    if api_key != expected:
        raise HTTPException(status_code=401, detail="API key non valida")

@router.post("/api/v1/backup/report", status_code=204)
def backup_report(report: BackupReport, x_api_key: str = Header(...)):
    _verify_api_key(report.vps_id, x_api_key)
    with db.get_db() as conn:
        server = conn.execute("SELECT vps_id FROM servers WHERE vps_id=?", (report.vps_id,)).fetchone()
        if not server:
            raise HTTPException(status_code=404, detail="VPS non registrata")
        conn.execute(
            """INSERT INTO backup_runs
               (vps_id, status, snapshot_id, size_gb, duration_s, downtime_s,
                error_msg, folders, disk_free_pct)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (report.vps_id, report.status, report.snapshot_id, report.size_gb,
             report.duration_s, report.downtime_s, report.error_msg,
             json.dumps(report.folders or []), report.disk_free_pct)
        )
```

- [ ] **Step 2: Scrivi `api/restore.py`**

```python
import hashlib
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
import db, config

router = APIRouter()

class RestoreReport(BaseModel):
    vps_id: str
    status: str
    checksum_ok: int = 0
    duration_s: Optional[int] = None
    error_msg: Optional[str] = None

def _verify_api_key(vps_id: str, api_key: str):
    expected = hashlib.sha256(f"{config.MASTER_SECRET}{vps_id}".encode()).hexdigest()
    if api_key != expected:
        raise HTTPException(status_code=401, detail="API key non valida")

@router.post("/api/v1/restore/report", status_code=204)
def restore_report(report: RestoreReport, x_api_key: str = Header(...)):
    _verify_api_key(report.vps_id, x_api_key)
    with db.get_db() as conn:
        last_run = conn.execute(
            "SELECT id FROM backup_runs WHERE vps_id=? ORDER BY id DESC LIMIT 1",
            (report.vps_id,)
        ).fetchone()
        backup_run_id = last_run["id"] if last_run else None
        conn.execute(
            """INSERT INTO restore_runs
               (vps_id, backup_run_id, status, checksum_ok, duration_s, error_msg)
               VALUES (?,?,?,?,?,?)""",
            (report.vps_id, backup_run_id, report.status, report.checksum_ok,
             report.duration_s, report.error_msg)
        )
```

- [ ] **Step 3: Scrivi i test**

```python
# tests/test_api_backup.py
import hashlib, pytest
from fastapi.testclient import TestClient
import config, db

def _make_app():
    from fastapi import FastAPI
    from api.backup import router
    app = FastAPI()
    app.include_router(router)
    return app

def _api_key(vps_id):
    return hashlib.sha256(f"{config.MASTER_SECRET}{vps_id}".encode()).hexdigest()

@pytest.fixture
def client(fresh_db):
    with db.get_db() as conn:
        conn.execute(
            "INSERT INTO servers (vps_id,hostname,cliente,api_key) VALUES (?,?,?,?)",
            ("vps-001", "test.host", "Test Srl", _api_key("vps-001"))
        )
    return TestClient(_make_app())

def test_backup_report_ok(client):
    r = client.post("/api/v1/backup/report",
        json={"vps_id":"vps-001","status":"ok","size_gb":4.2,"snapshot_id":"abc123"},
        headers={"x-api-key": _api_key("vps-001")})
    assert r.status_code == 204

def test_backup_report_wrong_key(client):
    r = client.post("/api/v1/backup/report",
        json={"vps_id":"vps-001","status":"ok"},
        headers={"x-api-key": "wrongkey"})
    assert r.status_code == 401

def test_backup_report_unknown_vps(client):
    r = client.post("/api/v1/backup/report",
        json={"vps_id":"vps-999","status":"ok"},
        headers={"x-api-key": _api_key("vps-999")})
    assert r.status_code == 404
```

- [ ] **Step 4: Lancia i test**

```bash
cd backup-monitor/master
pytest tests/test_api_backup.py -v
```
Atteso: 3 PASSED

- [ ] **Step 5: Commit**

```bash
git add backup-monitor/master/api/
git add backup-monitor/master/tests/test_api_backup.py
git commit -m "feat: backup/restore report endpoints with API key auth"
```

---

## Task 5: API — Servers List + Detail + Latest Snapshot

**Files:**
- Create: `backup-monitor/master/api/servers.py`
- Create: `backup-monitor/master/tests/test_api_servers.py`

- [ ] **Step 1: Scrivi `api/servers.py`**

```python
import hashlib, json
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
import db, config

router = APIRouter()

class RegisterServer(BaseModel):
    vps_id: str
    hostname: str
    cliente: str = ""
    os_name: str = ""
    os_version: str = ""
    folders: list[str] = []
    backup_hour: int = 2

@router.post("/api/v1/servers/register", status_code=201)
def register_server(payload: RegisterServer, x_api_key: str = Header(...)):
    # Autenticazione con MASTER_SECRET globale per la registrazione
    expected = hashlib.sha256(f"{config.MASTER_SECRET}register".encode()).hexdigest()
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Non autorizzato")
    vps_api_key = hashlib.sha256(f"{config.MASTER_SECRET}{payload.vps_id}".encode()).hexdigest()
    with db.get_db() as conn:
        conn.execute(
            """INSERT INTO servers (vps_id,hostname,cliente,os_name,os_version,folders,backup_hour,api_key)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(vps_id) DO UPDATE SET
               hostname=excluded.hostname, cliente=excluded.cliente,
               os_name=excluded.os_name, os_version=excluded.os_version,
               folders=excluded.folders, backup_hour=excluded.backup_hour""",
            (payload.vps_id, payload.hostname, payload.cliente,
             payload.os_name, payload.os_version,
             json.dumps(payload.folders), payload.backup_hour, vps_api_key)
        )
    return {"api_key": vps_api_key}

@router.get("/api/v1/servers")
def list_servers():
    with db.get_db() as conn:
        rows = conn.execute("""
            SELECT s.*,
                   br.status AS last_backup_status,
                   br.reported_at AS last_backup_at,
                   br.size_gb, br.duration_s, br.downtime_s,
                   br.snapshot_id, br.disk_free_pct,
                   rr.status AS last_restore_status
            FROM servers s
            LEFT JOIN backup_runs br ON br.id = (
                SELECT id FROM backup_runs WHERE vps_id=s.vps_id ORDER BY id DESC LIMIT 1)
            LEFT JOIN restore_runs rr ON rr.id = (
                SELECT id FROM restore_runs WHERE vps_id=s.vps_id ORDER BY id DESC LIMIT 1)
            ORDER BY s.vps_id
        """).fetchall()
    return [dict(r) for r in rows]

@router.get("/api/v1/servers/{vps_id}")
def server_detail(vps_id: str):
    with db.get_db() as conn:
        server = conn.execute("SELECT * FROM servers WHERE vps_id=?", (vps_id,)).fetchone()
        if not server:
            raise HTTPException(status_code=404, detail="VPS non trovata")
        runs = conn.execute(
            """SELECT br.*, rr.status AS restore_status, rr.checksum_ok
               FROM backup_runs br
               LEFT JOIN restore_runs rr ON rr.backup_run_id = br.id
               WHERE br.vps_id=? ORDER BY br.id DESC LIMIT 14""",
            (vps_id,)
        ).fetchall()
    return {"server": dict(server), "runs": [dict(r) for r in runs]}

@router.get("/api/v1/servers/{vps_id}/latest-snapshot")
def latest_snapshot(vps_id: str, x_api_key: str = Header(...)):
    expected = hashlib.sha256(f"{config.MASTER_SECRET}{vps_id}".encode()).hexdigest()
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="Non autorizzato")
    with db.get_db() as conn:
        run = conn.execute(
            "SELECT snapshot_id FROM backup_runs WHERE vps_id=? AND status='ok' ORDER BY id DESC LIMIT 1",
            (vps_id,)
        ).fetchone()
    if not run:
        raise HTTPException(status_code=404, detail="Nessun snapshot disponibile")
    return {"snapshot_id": run["snapshot_id"]}
```

- [ ] **Step 2: Test**

```python
# tests/test_api_servers.py
import hashlib, pytest
from fastapi.testclient import TestClient
import config

def _make_app():
    from fastapi import FastAPI
    from api.servers import router
    app = FastAPI(); app.include_router(router); return app

def _reg_key():
    return hashlib.sha256(f"{config.MASTER_SECRET}register".encode()).hexdigest()

@pytest.fixture
def client(fresh_db):
    return TestClient(_make_app())

def test_register_and_list(client):
    r = client.post("/api/v1/servers/register",
        json={"vps_id":"vps-001","hostname":"h1","cliente":"Test Srl","folders":["/home/Nativo"]},
        headers={"x-api-key": _reg_key()})
    assert r.status_code == 201
    assert "api_key" in r.json()

    r2 = client.get("/api/v1/servers")
    assert r2.status_code == 200
    assert len(r2.json()) == 1

def test_server_detail_not_found(client):
    r = client.get("/api/v1/servers/vps-999")
    assert r.status_code == 404
```

- [ ] **Step 3: Lancia test**

```bash
pytest tests/test_api_servers.py -v
```
Atteso: 2 PASSED

- [ ] **Step 4: Commit**

```bash
git add backup-monitor/master/api/servers.py backup-monitor/master/tests/test_api_servers.py
git commit -m "feat: servers register/list/detail/latest-snapshot endpoints"
```

---

## Task 6: Auth — Sessioni + TOTP

**Files:**
- Create: `backup-monitor/master/auth/sessions.py`
- Create: `backup-monitor/master/auth/totp.py`
- Create: `backup-monitor/master/tests/test_auth_totp.py`
- Create: `backup-monitor/master/tests/test_auth_sessions.py`

- [ ] **Step 1: Scrivi `auth/sessions.py`**

```python
import secrets, hashlib
from datetime import datetime, timedelta
import db

SESSION_HOURS = 8

def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(hours=SESSION_HOURS)).isoformat()
    with db.get_db() as conn:
        conn.execute(
            "INSERT INTO sessions (token, user_id, expires_at) VALUES (?,?,?)",
            (token, user_id, expires_at)
        )
    return token

def validate_session(token: str) -> dict | None:
    """Ritorna la riga user se la sessione è valida, None altrimenti."""
    with db.get_db() as conn:
        row = conn.execute(
            """SELECT s.user_id, s.expires_at, s.revoked, u.username, u.role
               FROM sessions s JOIN users u ON u.id = s.user_id
               WHERE s.token=?""",
            (token,)
        ).fetchone()
    if not row:
        return None
    if row["revoked"]:
        return None
    if datetime.fromisoformat(row["expires_at"]) < datetime.utcnow():
        return None
    return dict(row)

def revoke_session(token: str):
    with db.get_db() as conn:
        conn.execute("UPDATE sessions SET revoked=1 WHERE token=?", (token,))
```

- [ ] **Step 2: Scrivi `auth/totp.py`**

```python
import base64, json, secrets
import pyotp, qrcode, qrcode.image.svg
from io import BytesIO
from cryptography.fernet import Fernet
import config

def _fernet() -> Fernet:
    key = config.TOTP_ENCRYPTION_KEY
    if len(base64.urlsafe_b64decode(key + "==")) < 32:
        raise ValueError("TOTP_ENCRYPTION_KEY deve essere una Fernet key valida (32 byte base64url)")
    return Fernet(key)

def generate_secret() -> str:
    return pyotp.random_base32()

def encrypt_secret(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()

def decrypt_secret(enc: str) -> str:
    return _fernet().decrypt(enc.encode()).decode()

def verify_totp(totp_secret_enc: str, code: str) -> bool:
    plain = decrypt_secret(totp_secret_enc)
    totp = pyotp.TOTP(plain)
    return totp.verify(code, valid_window=1)

def totp_uri(secret: str, username: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name="BackupMonitor")

def totp_qr_svg(secret: str, username: str) -> str:
    uri = totp_uri(secret, username)
    img = qrcode.make(uri, image_factory=qrcode.image.svg.SvgImage)
    buf = BytesIO()
    img.save(buf)
    return buf.getvalue().decode()

def make_recovery_codes() -> list[str]:
    return [secrets.token_hex(5).upper() for _ in range(10)]
```

- [ ] **Step 3: Test TOTP**

```python
# tests/test_auth_totp.py
import pyotp
from auth.totp import (generate_secret, encrypt_secret, decrypt_secret,
                        verify_totp, make_recovery_codes)

def test_encrypt_decrypt_roundtrip():
    secret = generate_secret()
    enc = encrypt_secret(secret)
    assert decrypt_secret(enc) == secret

def test_verify_totp_valid():
    secret = generate_secret()
    enc = encrypt_secret(secret)
    code = pyotp.TOTP(secret).now()
    assert verify_totp(enc, code) is True

def test_verify_totp_invalid():
    secret = generate_secret()
    enc = encrypt_secret(secret)
    assert verify_totp(enc, "000000") is False

def test_recovery_codes_length():
    codes = make_recovery_codes()
    assert len(codes) == 10
    assert all(len(c) == 10 for c in codes)
```

- [ ] **Step 4: Test sessioni**

```python
# tests/test_auth_sessions.py
import db
from auth.sessions import create_session, validate_session, revoke_session
import bcrypt

@pytest.fixture
def user_id(fresh_db):
    pw = bcrypt.hashpw(b"password", bcrypt.gensalt()).decode()
    with db.get_db() as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?,?)", ("admin", pw)
        )
        return conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()["id"]

def test_create_and_validate(user_id):
    token = create_session(user_id)
    result = validate_session(token)
    assert result is not None
    assert result["username"] == "admin"

def test_revoke(user_id):
    token = create_session(user_id)
    revoke_session(token)
    assert validate_session(token) is None

def test_invalid_token(fresh_db):
    assert validate_session("nonexistent") is None
```

- [ ] **Step 5: Aggiungi import mancante a test_auth_sessions.py**

Aggiungi `import pytest` in cima a `tests/test_auth_sessions.py`.

- [ ] **Step 6: Lancia test**

```bash
pytest tests/test_auth_totp.py tests/test_auth_sessions.py -v
```
Atteso: tutti PASSED

- [ ] **Step 7: Commit**

```bash
git add backup-monitor/master/auth/ backup-monitor/master/tests/test_auth_*.py
git commit -m "feat: session management and TOTP 2FA"
```

---

## Task 7: Auth — WebAuthn (Passkey)

**Files:**
- Create: `backup-monitor/master/auth/webauthn.py`

- [ ] **Step 1: Scrivi `auth/webauthn.py`**

```python
import json, base64, secrets
from webauthn import (
    generate_registration_options, verify_registration_response,
    generate_authentication_options, verify_authentication_response,
    options_to_json,
)
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria, UserVerificationRequirement,
    PublicKeyCredentialDescriptor,
)
from webauthn.helpers.cose import COSEAlgorithmIdentifier
import config, db

RP_ID = config.MASTER_BASE_URL.split("://")[-1].split(":")[0].split("/")[0]
RP_NAME = "Backup Monitor"

def get_registration_options(user_id: int, username: str) -> dict:
    opts = generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=str(user_id).encode(),
        user_name=username,
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        supported_pub_key_algs=[COSEAlgorithmIdentifier.ECDSA_SHA_256],
    )
    return json.loads(options_to_json(opts))

def verify_and_store_credential(user_id: int, credential_json: dict, challenge: bytes):
    verification = verify_registration_response(
        credential=credential_json,
        expected_challenge=challenge,
        expected_rp_id=RP_ID,
        expected_origin=config.MASTER_BASE_URL,
    )
    new_cred = {
        "id": base64.b64encode(verification.credential_id).decode(),
        "public_key": base64.b64encode(verification.credential_public_key).decode(),
        "sign_count": verification.sign_count,
    }
    with db.get_db() as conn:
        row = conn.execute("SELECT passkey_creds FROM users WHERE id=?", (user_id,)).fetchone()
        creds = json.loads(row["passkey_creds"])
        creds.append(new_cred)
        conn.execute("UPDATE users SET passkey_creds=? WHERE id=?", (json.dumps(creds), user_id))

def get_authentication_options(username: str) -> dict:
    with db.get_db() as conn:
        row = conn.execute("SELECT passkey_creds FROM users WHERE username=?", (username,)).fetchone()
    if not row:
        return {}
    creds = json.loads(row["passkey_creds"])
    descriptors = [
        PublicKeyCredentialDescriptor(id=base64.b64decode(c["id"])) for c in creds
    ]
    opts = generate_authentication_options(
        rp_id=RP_ID,
        allow_credentials=descriptors,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    return json.loads(options_to_json(opts))

def verify_authentication(username: str, credential_json: dict, challenge: bytes) -> bool:
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT id, passkey_creds FROM users WHERE username=?", (username,)
        ).fetchone()
    if not row:
        return False
    creds = json.loads(row["passkey_creds"])
    cred_id_b64 = credential_json.get("id", "")
    stored = next((c for c in creds if c["id"] == cred_id_b64), None)
    if not stored:
        return False
    verify_authentication_response(
        credential=credential_json,
        expected_challenge=challenge,
        expected_rp_id=RP_ID,
        expected_origin=config.MASTER_BASE_URL,
        credential_public_key=base64.b64decode(stored["public_key"]),
        credential_current_sign_count=stored["sign_count"],
    )
    return True
```

- [ ] **Step 2: Commit** (WebAuthn è difficile da unit-testare senza un browser reale; viene testato end-to-end)

```bash
git add backup-monitor/master/auth/webauthn.py
git commit -m "feat: WebAuthn passkey registration and authentication"
```

---

## Task 8: API Auth endpoints + Rate Limiting + Main App

**Files:**
- Create: `backup-monitor/master/api/auth.py`
- Create: `backup-monitor/master/main.py`

- [ ] **Step 1: Scrivi `api/auth.py`**

```python
import bcrypt, json, secrets
from fastapi import APIRouter, Request, Response, HTTPException, Cookie
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel
from typing import Optional
import db
from auth.sessions import create_session, validate_session, revoke_session
from auth.totp import verify_totp
from auth.webauthn import get_authentication_options, verify_authentication

router = APIRouter()

# In-memory rate limiter semplice: {ip: [timestamp, ...]}
_failed: dict[str, list[float]] = {}

def _check_rate_limit(ip: str):
    import time
    now = time.time()
    attempts = [t for t in _failed.get(ip, []) if now - t < 600]
    _failed[ip] = attempts
    if len(attempts) >= 5:
        raise HTTPException(status_code=429, detail="Troppi tentativi. Riprova tra 10 minuti.")

def _record_failure(ip: str):
    import time
    _failed.setdefault(ip, []).append(time.time())

class LoginStep1(BaseModel):
    username: str
    password: str

class LoginStep2(BaseModel):
    username: str
    totp_code: str
    partial_token: str  # token temporaneo dopo step1

# Token temporanei (in-memory) per il flusso 2-step login
_partial_tokens: dict[str, str] = {}  # partial_token → username

@router.post("/auth/login/step1")
def login_step1(payload: LoginStep1, request: Request):
    _check_rate_limit(request.client.host)
    with db.get_db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE username=?", (payload.username,)
        ).fetchone()
    if not user or not bcrypt.checkpw(payload.password.encode(), user["password_hash"].encode()):
        _record_failure(request.client.host)
        raise HTTPException(status_code=401, detail="Credenziali non valide")
    if not user["totp_secret_enc"]:
        raise HTTPException(status_code=403, detail="2FA non configurato. Usa il CLI per completare il setup.")
    partial = secrets.token_urlsafe(16)
    _partial_tokens[partial] = payload.username
    return {"partial_token": partial}

@router.post("/auth/login/step2")
def login_step2(payload: LoginStep2, response: Response, request: Request):
    username = _partial_tokens.pop(payload.partial_token, None)
    if not username or username != payload.username:
        raise HTTPException(status_code=401, detail="Token temporaneo non valido")
    with db.get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not verify_totp(user["totp_secret_enc"], payload.totp_code):
        _record_failure(request.client.host)
        raise HTTPException(status_code=401, detail="Codice TOTP non valido")
    token = create_session(user["id"])
    response.set_cookie("session", token, httponly=True, samesite="strict", max_age=28800)
    return {"ok": True}

@router.post("/auth/logout")
def logout(response: Response, session: Optional[str] = Cookie(None)):
    if session:
        revoke_session(session)
    response.delete_cookie("session")
    return {"ok": True}

# Passkey challenge storage (in-memory, per username)
_webauthn_challenges: dict[str, bytes] = {}

@router.get("/auth/passkey/challenge")
def passkey_challenge(username: str):
    import base64
    opts = get_authentication_options(username)
    if not opts:
        raise HTTPException(status_code=404, detail="Nessuna passkey registrata")
    challenge_b64 = opts.get("challenge", "")
    _webauthn_challenges[username] = base64.urlsafe_b64decode(challenge_b64 + "==")
    return opts

@router.post("/auth/passkey/verify")
def passkey_verify(payload: dict, response: Response):
    username = payload.get("username", "")
    challenge = _webauthn_challenges.pop(username, None)
    if not challenge:
        raise HTTPException(status_code=400, detail="Challenge scaduta")
    ok = verify_authentication(username, payload.get("credential", {}), challenge)
    if not ok:
        raise HTTPException(status_code=401, detail="Autenticazione passkey fallita")
    with db.get_db() as conn:
        user = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
    token = create_session(user["id"])
    response.set_cookie("session", token, httponly=True, samesite="strict", max_age=28800)
    return {"ok": True}
```

- [ ] **Step 2: Scrivi `main.py`**

```python
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import db
from api.backup import router as backup_router
from api.restore import router as restore_router
from api.servers import router as servers_router
from api.auth import router as auth_router
from api.download import router as download_router
from alerts.engine import run_checks

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    task = asyncio.create_task(_alert_loop())
    yield
    task.cancel()

async def _alert_loop():
    while True:
        try:
            await asyncio.to_thread(run_checks)
        except Exception as e:
            print(f"[alert engine] errore: {e}")
        await asyncio.sleep(3600)

app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)

app.mount("/static", StaticFiles(directory="static"), name="static")

for r in [backup_router, restore_router, servers_router, auth_router, download_router]:
    app.include_router(r)

# Security headers
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response
```

- [ ] **Step 3: Commit**

```bash
git add backup-monitor/master/api/auth.py backup-monitor/master/main.py
git commit -m "feat: auth endpoints (login 2-step, passkey, logout) + main FastAPI app"
```

---

## Task 9: Download Streaming + JWT Link

**Files:**
- Create: `backup-monitor/master/api/download.py`
- Create: `backup-monitor/master/tests/test_download.py`

- [ ] **Step 1: Scrivi `api/download.py`**

```python
import subprocess, jwt, hashlib, json
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Cookie, Query
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Optional
import config, db
from auth.sessions import validate_session

router = APIRouter()

LARGE_GB = config.LARGE_FILE_THRESHOLD_GB

def _require_auth(session: Optional[str]) -> dict:
    if not session:
        raise HTTPException(status_code=401, detail="Non autenticato")
    user = validate_session(session)
    if not user:
        raise HTTPException(status_code=401, detail="Sessione scaduta")
    return user

def _snapshot_exists(vps_id: str, snapshot_id: str) -> float:
    """Ritorna size_gb dello snapshot, HTTPException se non trovato."""
    with db.get_db() as conn:
        row = conn.execute(
            "SELECT size_gb FROM backup_runs WHERE vps_id=? AND snapshot_id=? AND status='ok'",
            (vps_id, snapshot_id)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Snapshot non trovato")
    return row["size_gb"] or 0.0

def _restic_stream(snapshot_id: str, path: Optional[str] = None):
    cmd = ["restic", "dump", snapshot_id]
    if path:
        cmd.append(path)
    else:
        cmd.append("/")
    cmd += ["--quiet"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        while chunk := proc.stdout.read(65536):
            yield chunk
    finally:
        proc.wait()

@router.get("/api/v1/servers/{vps_id}/snapshots/{snapshot_id}/download")
def download_snapshot(vps_id: str, snapshot_id: str,
                       folder: Optional[str] = Query(None),
                       session: Optional[str] = Cookie(None)):
    _require_auth(session)
    size_gb = _snapshot_exists(vps_id, snapshot_id)

    if size_gb > LARGE_GB:
        # Genera link JWT temporaneo
        payload = {
            "vps_id": vps_id, "snapshot_id": snapshot_id,
            "folder": folder,
            "exp": datetime.utcnow() + timedelta(hours=24)
        }
        token = jwt.encode(payload, config.JWT_SECRET, algorithm="HS256")
        return JSONResponse({"download_url": f"/api/v1/download/token?t={token}", "expires_in_hours": 24})

    fname = f"{vps_id}_{snapshot_id[:8]}.tar.gz"
    return StreamingResponse(
        _restic_stream(snapshot_id, folder),
        media_type="application/gzip",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'}
    )

@router.get("/api/v1/download/token")
def download_by_token(t: str):
    try:
        payload = jwt.decode(t, config.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=410, detail="Link scaduto")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Token non valido")
    vps_id = payload["vps_id"]
    snapshot_id = payload["snapshot_id"]
    folder = payload.get("folder")
    _snapshot_exists(vps_id, snapshot_id)
    fname = f"{vps_id}_{snapshot_id[:8]}.tar.gz"
    return StreamingResponse(
        _restic_stream(snapshot_id, folder),
        media_type="application/gzip",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'}
    )
```

- [ ] **Step 2: Test**

```python
# tests/test_download.py
import hashlib, pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import config, db
import bcrypt
from auth.sessions import create_session

def _make_app():
    from fastapi import FastAPI
    from api.download import router
    app = FastAPI(); app.include_router(router); return app

@pytest.fixture
def authed_client(fresh_db):
    pw = bcrypt.hashpw(b"pw", bcrypt.gensalt()).decode()
    with db.get_db() as conn:
        conn.execute("INSERT INTO servers (vps_id,hostname,cliente,api_key) VALUES (?,?,?,?)",
                     ("vps-001","h","c","k"))
        conn.execute("INSERT INTO users (username,password_hash) VALUES (?,?)", ("admin",pw))
        uid = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()["id"]
        conn.execute(
            "INSERT INTO backup_runs (vps_id,status,snapshot_id,size_gb) VALUES (?,?,?,?)",
            ("vps-001","ok","snap123",1.0)
        )
    token = create_session(uid)
    client = TestClient(_make_app(), cookies={"session": token})
    return client

def test_download_small_snapshot(authed_client):
    with patch("api.download._restic_stream", return_value=iter([b"fake-tar-data"])):
        r = authed_client.get("/api/v1/servers/vps-001/snapshots/snap123/download")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/gzip"

def test_download_large_returns_jwt(authed_client, monkeypatch):
    monkeypatch.setattr(config, "LARGE_FILE_THRESHOLD_GB", 0.0)
    r = authed_client.get("/api/v1/servers/vps-001/snapshots/snap123/download")
    assert r.status_code == 200
    assert "download_url" in r.json()

def test_download_unauthenticated():
    client = TestClient(_make_app())
    r = client.get("/api/v1/servers/vps-001/snapshots/snap123/download")
    assert r.status_code == 401
```

- [ ] **Step 3: Lancia test**

```bash
pytest tests/test_download.py -v
```
Atteso: 3 PASSED

- [ ] **Step 4: Commit**

```bash
git add backup-monitor/master/api/download.py backup-monitor/master/tests/test_download.py
git commit -m "feat: download streaming + JWT link per archivi grandi"
```

---

## Task 10: Alert Engine

**Files:**
- Create: `backup-monitor/master/alerts/engine.py`
- Create: `backup-monitor/master/alerts/telegram.py`
- Create: `backup-monitor/master/alerts/email_notify.py`
- Create: `backup-monitor/master/alerts/whatsapp.py`
- Create: `backup-monitor/master/tests/test_alerts.py`

- [ ] **Step 1: Scrivi `alerts/telegram.py`**

```python
import httpx, config

def send_telegram(message: str):
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    httpx.post(url, json={"chat_id": config.TELEGRAM_CHAT_ID, "text": message}, timeout=10)
```

- [ ] **Step 2: Scrivi `alerts/whatsapp.py`**

```python
import httpx, urllib.parse, config

def send_whatsapp(message: str):
    if not config.CALLMEBOT_PHONE or not config.CALLMEBOT_APIKEY:
        return
    url = (f"https://api.callmebot.com/whatsapp.php"
           f"?phone={config.CALLMEBOT_PHONE}"
           f"&apikey={config.CALLMEBOT_APIKEY}"
           f"&text={urllib.parse.quote(message)}")
    httpx.get(url, timeout=10)
```

- [ ] **Step 3: Scrivi `alerts/email_notify.py`**

```python
import smtplib, config
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_alert_email(subject: str, body: str):
    if not config.SMTP_HOST or not config.ALERT_EMAIL_TO:
        return
    msg = MIMEMultipart()
    msg["From"] = config.SMTP_USER
    msg["To"] = config.ALERT_EMAIL_TO
    msg["Subject"] = f"[BackupMonitor] {subject}"
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as s:
        s.starttls()
        s.login(config.SMTP_USER, config.SMTP_PASSWORD)
        s.send_message(msg)

def send_daily_digest(summary: str):
    send_alert_email("Digest giornaliero backup", summary)
```

- [ ] **Step 4: Scrivi `alerts/engine.py`**

```python
from datetime import datetime, timedelta
import db, config
from alerts.telegram import send_telegram
from alerts.email_notify import send_alert_email
from alerts.whatsapp import send_whatsapp

def _notify(msg: str, critical: bool = False):
    send_telegram(msg)
    send_alert_email("Alert backup", msg)
    if critical:
        send_whatsapp(msg)

def run_checks():
    threshold = (datetime.utcnow() - timedelta(hours=config.STALE_HOURS)).isoformat()
    with db.get_db() as conn:
        servers = conn.execute("SELECT vps_id, cliente FROM servers").fetchall()
        for s in servers:
            vps_id, cliente = s["vps_id"], s["cliente"]

            # Check stale
            last_ok = conn.execute(
                "SELECT reported_at FROM backup_runs WHERE vps_id=? AND status='ok' ORDER BY id DESC LIMIT 1",
                (vps_id,)
            ).fetchone()
            if not last_ok or last_ok["reported_at"] < threshold:
                _notify(f"⚠️ STALE\nServer: {vps_id} ({cliente})\nNessun backup riuscito nelle ultime {config.STALE_HOURS}h")

            # Check ultimo backup fallito
            last_run = conn.execute(
                "SELECT status, error_msg FROM backup_runs WHERE vps_id=? ORDER BY id DESC LIMIT 1",
                (vps_id,)
            ).fetchone()
            if last_run and last_run["status"] == "failed":
                msg = (f"🔴 BACKUP FALLITO\nServer: {vps_id} ({cliente})\n"
                       f"Errore: {last_run['error_msg'] or 'sconosciuto'}\n"
                       f"→ {config.MASTER_BASE_URL}/servers/{vps_id}")
                _notify(msg, critical=True)

            # Check restore test fallito
            last_restore = conn.execute(
                "SELECT status FROM restore_runs WHERE vps_id=? ORDER BY id DESC LIMIT 1",
                (vps_id,)
            ).fetchone()
            if last_restore and last_restore["status"] == "failed":
                _notify(f"🧪 RESTORE TEST FALLITO\nServer: {vps_id} ({cliente})\n"
                        f"→ {config.MASTER_BASE_URL}/servers/{vps_id}", critical=True)
```

- [ ] **Step 5: Test alert engine**

```python
# tests/test_alerts.py
from unittest.mock import patch, MagicMock
import db, config
from alerts.engine import run_checks

def test_stale_server_triggers_notify(fresh_db):
    with db.get_db() as conn:
        conn.execute("INSERT INTO servers (vps_id,hostname,cliente,api_key) VALUES (?,?,?,?)",
                     ("vps-001","h","TestSrl","k"))
        # nessuna backup_run → stale
    with patch("alerts.engine.send_telegram") as mock_tg, \
         patch("alerts.engine.send_alert_email") as mock_em:
        run_checks()
    mock_tg.assert_called_once()
    assert "STALE" in mock_tg.call_args[0][0]

def test_ok_server_no_alert(fresh_db):
    with db.get_db() as conn:
        conn.execute("INSERT INTO servers (vps_id,hostname,cliente,api_key) VALUES (?,?,?,?)",
                     ("vps-001","h","TestSrl","k"))
        conn.execute(
            "INSERT INTO backup_runs (vps_id,status,reported_at) VALUES (?,?,datetime('now'))",
            ("vps-001","ok")
        )
    with patch("alerts.engine.send_telegram") as mock_tg:
        run_checks()
    mock_tg.assert_not_called()
```

- [ ] **Step 6: Lancia test**

```bash
pytest tests/test_alerts.py -v
```
Atteso: 2 PASSED

- [ ] **Step 7: Commit**

```bash
git add backup-monitor/master/alerts/ backup-monitor/master/tests/test_alerts.py
git commit -m "feat: alert engine (stale/failed/restore) + Telegram/Email/WhatsApp"
```

---

## Task 11: Dashboard HTML (Jinja2)

**Files:**
- Create: `backup-monitor/master/templates/base.html`
- Create: `backup-monitor/master/templates/login.html`
- Create: `backup-monitor/master/templates/dashboard.html`
- Create: `backup-monitor/master/templates/server_detail.html`
- Create: `backup-monitor/master/templates/setup_2fa.html`
- Create: `backup-monitor/master/static/style.css`
- Modify: `backup-monitor/master/main.py` — aggiunge routes HTML

- [ ] **Step 1: Scrivi `templates/base.html`**

```html
<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{% block title %}Backup Monitor{% endblock %}</title>
<link rel="stylesheet" href="/static/style.css">
</head>
<body>
{% if user %}
<nav>
  <span class="logo">🛡️ Backup Monitor</span>
  <span class="nav-user">{{ user.username }} ({{ user.role }})</span>
  <form method="post" action="/auth/logout" style="display:inline">
    <button type="submit" class="btn-link">Logout</button>
  </form>
</nav>
{% endif %}
<main>{% block content %}{% endblock %}</main>
</body>
</html>
```

- [ ] **Step 2: Scrivi `templates/login.html`**

```html
{% extends "base.html" %}
{% block title %}Login — Backup Monitor{% endblock %}
{% block content %}
<div class="login-box">
  <h1>🛡️ Backup Monitor</h1>
  {% if error %}<p class="error">{{ error }}</p>{% endif %}

  <button id="btn-passkey" class="btn-primary btn-passkey">🔑 Accedi con Passkey</button>
  <div class="divider">oppure</div>

  <form id="form-step1" method="post" action="/auth/login/step1-form">
    <label>Username<input name="username" type="text" required autocomplete="username"></label>
    <label>Password<input name="password" type="password" required autocomplete="current-password"></label>
    <button type="submit" class="btn-primary">Continua →</button>
  </form>
</div>
<script>
document.getElementById('btn-passkey').onclick = async () => {
  const username = prompt('Username:');
  if (!username) return;
  const opts = await fetch('/auth/passkey/challenge?username=' + username).then(r=>r.json());
  opts.challenge = Uint8Array.from(atob(opts.challenge.replace(/-/g,'+').replace(/_/g,'/')), c=>c.charCodeAt(0));
  opts.allowCredentials = (opts.allowCredentials||[]).map(c=>({...c,id:Uint8Array.from(atob(c.id.replace(/-/g,'+').replace(/_/g,'/')),c=>c.charCodeAt(0))}));
  const cred = await navigator.credentials.get({publicKey: opts});
  const payload = {
    username,
    credential: {
      id: cred.id,
      rawId: btoa(String.fromCharCode(...new Uint8Array(cred.rawId))),
      response: {
        clientDataJSON: btoa(String.fromCharCode(...new Uint8Array(cred.response.clientDataJSON))),
        authenticatorData: btoa(String.fromCharCode(...new Uint8Array(cred.response.authenticatorData))),
        signature: btoa(String.fromCharCode(...new Uint8Array(cred.response.signature))),
      },
      type: cred.type,
    }
  };
  const res = await fetch('/auth/passkey/verify', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
  if (res.ok) location.href='/';
  else alert('Autenticazione passkey fallita');
};
</script>
{% endblock %}
```

- [ ] **Step 3: Scrivi `templates/dashboard.html`**

```html
{% extends "base.html" %}
{% block title %}Dashboard — Backup Monitor{% endblock %}
{% block content %}
<div class="kpis">
  <div class="kpi ok">{{ stats.ok }}<small>✅ OK</small></div>
  <div class="kpi failed">{{ stats.failed }}<small>❌ Falliti</small></div>
  <div class="kpi stale">{{ stats.stale }}<small>⚠️ Stale</small></div>
  <div class="kpi">{{ stats.restore_pct }}%<small>🧪 Restore OK</small></div>
</div>

<div class="filters">
  <input type="search" id="search" placeholder="🔍 Cerca server, cliente...">
  <button class="filter-btn active" data-filter="all">Tutti</button>
  <button class="filter-btn" data-filter="ok">✅ OK</button>
  <button class="filter-btn" data-filter="failed">❌ Falliti</button>
  <button class="filter-btn" data-filter="stale">⚠️ Stale</button>
</div>

<table class="servers-table">
<thead><tr>
  <th>Server</th><th>Cliente</th><th>OS</th><th>Stato</th>
  <th>Orario</th><th>Ultimo Backup</th><th>Cartelle</th>
  <th>Dim.</th><th>Disco VPS</th><th>Restore</th><th></th>
</tr></thead>
<tbody>
{% for s in servers %}
<tr class="row-{{ s.row_status }}" data-status="{{ s.row_status }}">
  <td class="mono">{{ s.vps_id }}</td>
  <td>{{ s.cliente }}</td>
  <td><span class="os-badge os-{{ s.os_slug }}">🐧 {{ s.os_name }} {{ s.os_version }}</span></td>
  <td><span class="badge-{{ s.row_status }}">{{ s.status_icon }}</span></td>
  <td class="mono">{{ "%02d:00"|format(s.backup_hour) }}</td>
  <td>{{ s.last_backup_at or '—' }}</td>
  <td>{% for f in s.folders_list %}<span class="folder-badge">{{ f|basename }}</span>{% endfor %}</td>
  <td>{{ "%.1f GB"|format(s.size_gb) if s.size_gb else '—' }}</td>
  <td>
    {% if s.disk_free_pct is not none %}
    <span class="disk-{{ s.disk_color }}">{{ s.disk_free_pct|int }}% lib.</span>
    <div class="disk-bar"><div class="disk-fill disk-fill-{{ s.disk_color }}" style="width:{{ 100 - s.disk_free_pct|int }}%"></div></div>
    {% else %}—{% endif %}
  </td>
  <td>{{ '✅' if s.last_restore_status == 'ok' else ('❌' if s.last_restore_status == 'failed' else '—') }}</td>
  <td><a href="/servers/{{ s.vps_id }}">›</a></td>
</tr>
{% endfor %}
</tbody>
</table>

<script>
const search = document.getElementById('search');
const rows = document.querySelectorAll('tbody tr');
const btns = document.querySelectorAll('.filter-btn');
let activeFilter = 'all';

function applyFilters() {
  const q = search.value.toLowerCase();
  rows.forEach(r => {
    const text = r.textContent.toLowerCase();
    const matchQ = !q || text.includes(q);
    const matchF = activeFilter === 'all' || r.dataset.status === activeFilter;
    r.style.display = matchQ && matchF ? '' : 'none';
  });
}
search.addEventListener('input', applyFilters);
btns.forEach(b => b.addEventListener('click', () => {
  btns.forEach(x => x.classList.remove('active'));
  b.classList.add('active');
  activeFilter = b.dataset.filter;
  applyFilters();
}));
</script>
{% endblock %}
```

- [ ] **Step 4: Scrivi `templates/server_detail.html`**

```html
{% extends "base.html" %}
{% block title %}{{ server.vps_id }} — Backup Monitor{% endblock %}
{% block content %}
<p><a href="/">← Tutti i server</a></p>
<h2 class="mono">{{ server.vps_id }}</h2>
<p>{{ server.cliente }} &nbsp; <span class="os-badge os-{{ server.os_slug }}">🐧 {{ server.os_name }} {{ server.os_version }}</span></p>

<div class="kpis">
  <div class="kpi"><small>Ultimo backup</small>{{ last_run.reported_at or '—' }}</div>
  <div class="kpi"><small>Dimensione</small>{{ "%.1f GB"|format(last_run.size_gb) if last_run and last_run.size_gb else '—' }}</div>
  <div class="kpi"><small>Durata</small>{{ last_run.duration_s or '—' }}s</div>
  <div class="kpi"><small>Downtime</small>{{ last_run.downtime_s or '—' }}s</div>
  <div class="kpi"><small>Disco libero</small>{{ last_run.disk_free_pct|int }}% {% if last_run and last_run.disk_free_pct else '' %}</div>
</div>

<h3>Cartelle backuppate</h3>
<div class="folders-list">
{% for f in server.folders_list %}
<div class="folder-row">
  <span class="mono">📁 {{ f }}</span>
  <a class="btn-sm" href="/api/v1/servers/{{ server.vps_id }}/snapshots/{{ last_snapshot_id }}/download?folder={{ f }}">⬇ .tar.gz</a>
</div>
{% endfor %}
</div>

<h3>Storico ultimi backup</h3>
<table class="servers-table">
<thead><tr>
  <th>Data</th><th>Stato</th><th>Dim.</th><th>Durata</th><th>Downtime</th><th>Restore</th><th>Download</th><th>Log</th>
</tr></thead>
<tbody>
{% for r in runs %}
<tr class="row-{{ 'ok' if r.status == 'ok' else 'failed' }}">
  <td>{{ r.reported_at }}</td>
  <td>{{ '✅ OK' if r.status == 'ok' else '❌ FAILED' }}</td>
  <td>{{ "%.1f GB"|format(r.size_gb) if r.size_gb else '—' }}</td>
  <td>{{ r.duration_s or '—' }}s</td>
  <td>{{ r.downtime_s or '—' }}s</td>
  <td>{{ '✅' if r.restore_status == 'ok' else ('❌' if r.restore_status == 'failed' else '—') }}</td>
  <td>
    {% if r.status == 'ok' %}
    <a class="btn-sm" href="/api/v1/servers/{{ server.vps_id }}/snapshots/{{ r.snapshot_id }}/download">⬇ Tutto</a>
    <select class="folder-select" onchange="if(this.value) location.href='/api/v1/servers/{{ server.vps_id }}/snapshots/{{ r.snapshot_id }}/download?folder='+this.value">
      <option value="">Cartella…</option>
      {% for f in server.folders_list %}<option value="{{ f }}">{{ f|basename }}</option>{% endfor %}
    </select>
    {% else %}—{% endif %}
  </td>
  <td>{{ r.error_msg or '' }}</td>
</tr>
{% endfor %}
</tbody>
</table>
{% endblock %}
```

- [ ] **Step 5: Aggiungi routes HTML a `main.py`**

Aggiungi dopo gli import esistenti:

```python
from fastapi import Cookie
from fastapi.responses import RedirectResponse
from auth.sessions import validate_session
import json

templates = Jinja2Templates(directory="templates")
templates.env.filters["basename"] = lambda p: p.split("/")[-1]

def _os_slug(os_name: str) -> str:
    n = os_name.lower()
    if "ubuntu" in n: return "ubuntu"
    if "debian" in n: return "debian"
    if "centos" in n: return "centos"
    if "alma" in n: return "alma"
    if "rocky" in n: return "rocky"
    return "unknown"

def _disk_color(pct: float | None) -> str:
    if pct is None: return "unknown"
    if pct > 40: return "green"
    if pct > 20: return "yellow"
    return "red"

def _get_user(session: str | None) -> dict | None:
    return validate_session(session) if session else None

@app.get("/")
def dashboard(session: str | None = Cookie(None)):
    user = _get_user(session)
    if not user:
        return RedirectResponse("/login")
    import api.servers as sv
    servers_raw = sv.list_servers()
    stats = {"ok": 0, "failed": 0, "stale": 0, "restore_pct": 0}
    restore_total, restore_ok = 0, 0
    from datetime import datetime, timedelta
    stale_threshold = (datetime.utcnow() - timedelta(hours=config.STALE_HOURS)).isoformat()
    for s in servers_raw:
        s["folders_list"] = json.loads(s.get("folders") or "[]")
        s["os_slug"] = _os_slug(s.get("os_name") or "")
        s["disk_color"] = _disk_color(s.get("disk_free_pct"))
        last_at = s.get("last_backup_at") or ""
        if s.get("last_backup_status") == "ok" and last_at > stale_threshold:
            s["row_status"] = "ok"; s["status_icon"] = "✅ OK"; stats["ok"] += 1
        elif s.get("last_backup_status") == "failed":
            s["row_status"] = "failed"; s["status_icon"] = "❌ FAILED"; stats["failed"] += 1
        else:
            s["row_status"] = "stale"; s["status_icon"] = "⚠️ STALE"; stats["stale"] += 1
        if s.get("last_restore_status"):
            restore_total += 1
            if s["last_restore_status"] == "ok": restore_ok += 1
    stats["restore_pct"] = int(restore_ok * 100 / restore_total) if restore_total else 0
    return templates.TemplateResponse("dashboard.html", {"request": {}, "user": user, "servers": servers_raw, "stats": stats})

@app.get("/servers/{vps_id}")
def server_detail_page(vps_id: str, session: str | None = Cookie(None)):
    user = _get_user(session)
    if not user:
        return RedirectResponse("/login")
    import api.servers as sv
    data = sv.server_detail(vps_id)
    server = data["server"]
    server["folders_list"] = json.loads(server.get("folders") or "[]")
    server["os_slug"] = _os_slug(server.get("os_name") or "")
    runs = data["runs"]
    last_run = runs[0] if runs else None
    last_snapshot_id = last_run["snapshot_id"] if last_run and last_run.get("snapshot_id") else ""
    return templates.TemplateResponse("server_detail.html", {
        "request": {}, "user": user, "server": server,
        "runs": runs, "last_run": last_run, "last_snapshot_id": last_snapshot_id
    })

@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})
```

- [ ] **Step 6: Scrivi `static/style.css`** (dark theme, stesso look del mockup)

```css
:root {
  --bg: #0f1117; --bg2: #161b22; --border: #30363d;
  --text: #e6edf3; --muted: #7d8590; --green: #3fb950;
  --red: #f85149; --yellow: #d29922; --blue: #58a6ff;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--text); font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; font-size: 14px; }
nav { display:flex; align-items:center; gap:16px; padding:12px 24px; background:var(--bg2); border-bottom:1px solid var(--border); }
.logo { font-weight:700; font-size:1.1em; }
.nav-user { margin-left:auto; color:var(--muted); }
main { padding:20px 24px; }
.kpis { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:20px; }
.kpi { background:var(--bg2); border:1px solid var(--border); border-radius:8px; padding:14px; text-align:center; font-size:1.8em; font-weight:700; }
.kpi small { display:block; font-size:0.45em; color:var(--muted); margin-top:4px; }
.kpi.ok { border-color:var(--green); color:var(--green); }
.kpi.failed { border-color:var(--red); color:var(--red); }
.kpi.stale { border-color:var(--yellow); color:var(--yellow); }
.filters { display:flex; gap:8px; margin-bottom:12px; flex-wrap:wrap; align-items:center; }
.filters input { background:var(--bg2); border:1px solid var(--border); color:var(--text); padding:6px 12px; border-radius:6px; flex:1; max-width:260px; }
.filter-btn { background:var(--bg2); border:1px solid var(--border); color:var(--muted); padding:5px 12px; border-radius:6px; cursor:pointer; }
.filter-btn.active { background:var(--blue); color:#fff; border-color:var(--blue); }
.servers-table { width:100%; border-collapse:collapse; font-size:0.85em; }
.servers-table th { color:var(--muted); text-transform:uppercase; font-size:0.78em; padding:8px 6px; border-bottom:1px solid var(--border); text-align:left; }
.servers-table td { padding:7px 6px; border-bottom:1px solid #21262d; }
.servers-table tr:hover td { background:var(--bg2); }
.row-failed td:first-child { color:var(--red); }
.row-stale td:first-child { color:var(--yellow); }
.badge-ok { background:rgba(63,185,80,.15); color:var(--green); border-radius:4px; padding:2px 7px; }
.badge-failed { background:rgba(248,81,73,.15); color:var(--red); border-radius:4px; padding:2px 7px; }
.badge-stale { background:rgba(210,153,34,.15); color:var(--yellow); border-radius:4px; padding:2px 7px; }
.os-badge { border-radius:4px; padding:2px 8px; font-size:0.85em; }
.os-ubuntu { background:#1f3a5f; color:var(--blue); }
.os-debian { background:#2d1f5f; color:#b87ef7; }
.os-centos { background:#3a1f1f; color:#f78080; }
.os-alma { background:#1f2f3a; color:#79c0ff; }
.os-rocky { background:#2a2a1f; color:#e3b341; }
.os-unknown { background:var(--border); color:var(--muted); }
.folder-badge { background:#21262d; color:#c9d1d9; border-radius:3px; padding:1px 6px; font-family:monospace; margin-right:3px; }
.disk-bar { width:50px; height:4px; background:#21262d; border-radius:2px; margin-top:3px; display:inline-block; vertical-align:middle; margin-left:4px; }
.disk-fill { height:100%; border-radius:2px; }
.disk-green { color:var(--green); } .disk-fill-green { background:var(--green); }
.disk-yellow { color:var(--yellow); } .disk-fill-yellow { background:var(--yellow); }
.disk-red { color:var(--red); } .disk-fill-red { background:var(--red); }
.mono { font-family:monospace; }
.login-box { max-width:380px; margin:80px auto; background:var(--bg2); border:1px solid var(--border); border-radius:10px; padding:32px; }
.login-box h1 { text-align:center; margin-bottom:24px; }
.login-box label { display:block; margin-bottom:12px; }
.login-box input { display:block; width:100%; margin-top:4px; background:var(--bg); border:1px solid var(--border); color:var(--text); padding:8px 12px; border-radius:6px; }
.btn-primary { width:100%; background:var(--blue); color:#fff; border:none; padding:10px; border-radius:6px; cursor:pointer; font-size:1em; margin-top:8px; }
.btn-passkey { background:#2a3a2a; color:var(--green); border:1px solid var(--green); }
.divider { text-align:center; color:var(--muted); margin:14px 0; }
.error { color:var(--red); margin-bottom:12px; }
.folders-list .folder-row { display:flex; align-items:center; gap:12px; padding:8px; background:var(--bg2); border:1px solid var(--border); border-radius:6px; margin-bottom:6px; }
.btn-sm { background:#1c2d3a; color:var(--blue); border:1px solid #1f6feb; border-radius:4px; padding:3px 10px; font-size:0.82em; text-decoration:none; }
.btn-link { background:none; border:none; color:var(--blue); cursor:pointer; }
```

- [ ] **Step 7: Commit**

```bash
git add backup-monitor/master/templates/ backup-monitor/master/static/ backup-monitor/master/main.py
git commit -m "feat: Jinja2 dashboard + server detail pages with dark theme"
```

---

## Task 12: CLI manage.py + Setup 2FA

**Files:**
- Create: `backup-monitor/master/manage.py`

- [ ] **Step 1: Scrivi `manage.py`**

```python
#!/usr/bin/env python3
"""CLI per gestione utenti. Uso: python manage.py create-user --username admin"""
import argparse, getpass, bcrypt, json, sys
import db
from auth.totp import generate_secret, encrypt_secret, make_recovery_codes, totp_uri

db.init_db()

def cmd_create_user(args):
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Conferma password: ")
    if password != confirm:
        print("Le password non coincidono."); sys.exit(1)
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()

    totp_plain = generate_secret()
    totp_enc = encrypt_secret(totp_plain)
    recovery = make_recovery_codes()
    recovery_hashes = [bcrypt.hashpw(c.encode(), bcrypt.gensalt()).decode() for c in recovery]

    with db.get_db() as conn:
        conn.execute(
            "INSERT INTO users (username,password_hash,totp_secret_enc,recovery_codes,role) VALUES (?,?,?,?,?)",
            (args.username, pw_hash, totp_enc, json.dumps(recovery_hashes), args.role)
        )
    print(f"\n✅ Utente '{args.username}' creato.")
    print(f"\n📱 Configura il 2FA scansionando questo URI con Google Authenticator / Authy:")
    print(f"\n   {totp_uri(totp_plain, args.username)}\n")
    print("💾 Codici di recupero (conservali in un posto sicuro — mostrati una sola volta):")
    for c in recovery:
        print(f"   {c}")

parser = argparse.ArgumentParser()
sub = parser.add_subparsers(dest="cmd")
p_create = sub.add_parser("create-user")
p_create.add_argument("--username", required=True)
p_create.add_argument("--role", default="admin", choices=["admin","readonly"])

args = parser.parse_args()
if args.cmd == "create-user":
    cmd_create_user(args)
else:
    parser.print_help()
```

- [ ] **Step 2: Test manuale rapido (non automatizzato — richiede input interattivo)**

```bash
cd backup-monitor/master
echo -e "TestPass1!\nTestPass1!" | python manage.py create-user --username admin
```
Atteso: stampa URI TOTP e 10 codici di recupero

- [ ] **Step 3: Commit**

```bash
git add backup-monitor/master/manage.py
git commit -m "feat: manage.py CLI create-user with TOTP setup"
```

---

## Task 13: Ansible Playbook Deploy

**Files:**
- Create: `backup-monitor/ansible/inventory.yml`
- Create: `backup-monitor/ansible/playbook.yml`
- Create: `backup-monitor/ansible/roles/backup-agent/tasks/main.yml`
- Create: `backup-monitor/ansible/roles/backup-agent/defaults/main.yml`
- Create: `backup-monitor/ansible/roles/backup-agent/templates/restic.env.j2`
- Create: `backup-monitor/ansible/roles/backup-agent/templates/backup.sh.j2`
- Create: `backup-monitor/ansible/roles/backup-agent/templates/restore_test.sh.j2`

- [ ] **Step 1: Scrivi `ansible/inventory.yml`**

```yaml
# Esempio — adatta con i tuoi IP reali
all:
  children:
    vps:
      hosts:
        vps-001:
          ansible_host: 1.2.3.4
          vps_id: vps-001
          cliente: "Rossi Srl"
          backup_folders: "/home/Nativo"
          teamsystem_service: teamsystem
          os_name: Ubuntu
          os_version: "22.04"
        vps-002:
          ansible_host: 1.2.3.5
          vps_id: vps-002
          cliente: "Bianchi & Co"
          backup_folders: "/home/Nativo /home/Nativo_1 /home/GecomNativo"
          teamsystem_service: teamsystem
          os_name: Ubuntu
          os_version: "22.04"
      vars:
        ansible_user: root
        ansible_ssh_private_key_file: ~/.ssh/id_ed25519
```

- [ ] **Step 2: Scrivi `ansible/roles/backup-agent/defaults/main.yml`**

```yaml
restic_version: "0.17.3"
master_url: "https://master.tuo-dominio.it:8080"
master_secret: "{{ vault_master_secret }}"    # in ansible-vault
s3_endpoint: "https://eu2.contabostorage.com"
s3_bucket: "backups"
restic_password: "{{ vault_restic_password }}" # in ansible-vault
s3_access_key: "{{ vault_s3_access_key }}"
s3_secret_key: "{{ vault_s3_secret_key }}"
backup_hour: 2
restore_hour: 3
restore_minute: 30
```

- [ ] **Step 3: Scrivi `ansible/roles/backup-agent/templates/restic.env.j2`**

```bash
# /etc/restic/restic.env — generato da Ansible, non modificare manualmente
export RESTIC_REPOSITORY="s3:{{ s3_endpoint }}/{{ s3_bucket }}/{{ vps_id }}"
export RESTIC_PASSWORD="{{ restic_password }}"
export AWS_ACCESS_KEY_ID="{{ s3_access_key }}"
export AWS_SECRET_ACCESS_KEY="{{ s3_secret_key }}"
export MASTER_URL="{{ master_url }}"
export VPS_ID="{{ vps_id }}"
export API_KEY="{{ api_key }}"
export TEAMSYSTEM_SERVICE="{{ teamsystem_service }}"
export BACKUP_FOLDERS="{{ backup_folders }}"
```

- [ ] **Step 4: Scrivi `ansible/roles/backup-agent/tasks/main.yml`**

```yaml
- name: Scarica restic binary
  get_url:
    url: "https://github.com/restic/restic/releases/download/v{{ restic_version }}/restic_{{ restic_version }}_linux_amd64.bz2"
    dest: /tmp/restic.bz2
    mode: '0644'

- name: Decomprimi restic
  shell: bunzip2 -f /tmp/restic.bz2 && mv /tmp/restic /usr/local/bin/restic && chmod +x /usr/local/bin/restic
  args:
    creates: /usr/local/bin/restic

- name: Genera api_key per questo VPS
  set_fact:
    api_key: "{{ (master_secret + vps_id) | hash('sha256') }}"

- name: Crea directory /etc/restic
  file:
    path: /etc/restic
    state: directory
    mode: '0700'
    owner: root

- name: Scrivi restic.env
  template:
    src: restic.env.j2
    dest: "/etc/restic/restic.env"
    mode: '0600'
    owner: root

- name: Scrivi script backup
  template:
    src: backup.sh.j2
    dest: /usr/local/bin/backup-teamsystem.sh
    mode: '0750'
    owner: root

- name: Scrivi script restore test
  template:
    src: restore_test.sh.j2
    dest: /usr/local/bin/restore-test-teamsystem.sh
    mode: '0750'
    owner: root

- name: Inizializza repository restic S3
  shell: |
    source /etc/restic/restic.env
    restic snapshots > /dev/null 2>&1 || restic init
  args:
    executable: /bin/bash
  register: restic_init
  changed_when: "'created restic repository' in restic_init.stdout"

- name: Registra VPS sul Master Service
  uri:
    url: "{{ master_url }}/api/v1/servers/register"
    method: POST
    headers:
      X-API-Key: "{{ (master_secret + 'register') | hash('sha256') }}"
      Content-Type: application/json
    body_format: json
    body:
      vps_id: "{{ vps_id }}"
      hostname: "{{ inventory_hostname }}"
      cliente: "{{ cliente }}"
      os_name: "{{ os_name }}"
      os_version: "{{ os_version }}"
      folders: "{{ backup_folders.split() }}"
      backup_hour: "{{ backup_hour }}"
    status_code: [200, 201]

- name: Cron backup alle {{ backup_hour }}:00
  cron:
    name: "teamsystem-backup"
    hour: "{{ backup_hour }}"
    minute: "0"
    job: "/usr/local/bin/backup-teamsystem.sh >> /var/log/backup-teamsystem.log 2>&1"
    user: root

- name: Cron restore test alle {{ restore_hour }}:{{ restore_minute }}
  cron:
    name: "teamsystem-restore-test"
    hour: "{{ restore_hour }}"
    minute: "{{ restore_minute }}"
    job: "/usr/local/bin/restore-test-teamsystem.sh >> /var/log/restore-test.log 2>&1"
    user: root
```

- [ ] **Step 5: Scrivi `ansible/playbook.yml`**

```yaml
---
- name: Deploy backup agent su tutte le VPS
  hosts: vps
  become: yes
  roles:
    - backup-agent
```

- [ ] **Step 6: Verifica sintassi Ansible**

```bash
cd backup-monitor/ansible
ansible-playbook playbook.yml --syntax-check
```
Atteso: `playbook: playbook.yml` senza errori

- [ ] **Step 7: Commit**

```bash
git add backup-monitor/ansible/
git commit -m "feat: Ansible playbook deploy restic + cron su 100 VPS"
```

---

## Task 14: Integrazione finale + avvio

**Files:**
- Create: `backup-monitor/master/.env.example`
- Create: `backup-monitor/README.md` (solo istruzioni avvio — non documentazione)

- [ ] **Step 1: Scrivi `.env.example`**

```bash
MASTER_SECRET=cambia-con-stringa-casuale-lunga
JWT_SECRET=cambia-con-altra-stringa-casuale
TOTP_ENCRYPTION_KEY=genera-con--python-c--from-cryptography.fernet-import-Fernet-print(Fernet.generate_key().decode())
DB_PATH=backup_monitor.db
MASTER_BASE_URL=https://master.tuo-dominio.it:8080

TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
ALERT_EMAIL_TO=
CALLMEBOT_PHONE=
CALLMEBOT_APIKEY=
STALE_HOURS=25
LARGE_FILE_THRESHOLD_GB=5.0
```

- [ ] **Step 2: Lancia tutti i test**

```bash
cd backup-monitor/master
pytest tests/ -v --tb=short
```
Atteso: tutti PASSED

- [ ] **Step 3: Avvia in locale per verifica visuale**

```bash
cd backup-monitor/master
cp .env.example .env
# Modifica .env con valori reali
export $(cat .env | xargs)
python manage.py create-user --username admin
uvicorn main:app --host 0.0.0.0 --port 8080 --reload
```
Apri `http://localhost:8080` → pagina login → inserisci credenziali + TOTP → dashboard

- [ ] **Step 4: Commit finale**

```bash
git add backup-monitor/master/.env.example
git commit -m "feat: backup monitor completo — dashboard, alert, download, deploy Ansible"
```

---

## Self-Review

**Copertura spec:**
- ✅ Script bash backup (stop/start TeamSystem, restic, POST report)
- ✅ Script bash restore test (checksum SHA256, POST report)
- ✅ S3 Contabo (RESTIC_REPOSITORY con endpoint Contabo)
- ✅ Master Service API (tutti gli endpoint elencati nella spec)
- ✅ Dashboard tabellare (OS badge dinamico, disco, cartelle, orario, stato)
- ✅ Pagina dettaglio server (KPI, storico, download per cartella e snapshot)
- ✅ Download streaming + JWT per archivi >5 GB
- ✅ Alert engine (stale >25h, backup fallito, restore fallito)
- ✅ Telegram, Email, WhatsApp (Callmebot)
- ✅ Auth username + password + TOTP 2FA obbligatorio
- ✅ Auth Passkey WebAuthn (FIDO2)
- ✅ Sessioni httpOnly 8h con revoca
- ✅ Rate limiting login (5 tentativi / 10 min)
- ✅ Security headers
- ✅ CLI create-user con setup TOTP
- ✅ Ansible playbook (100 VPS, cron 02:00 e 03:30)
- ✅ DB 5 tabelle (servers, backup_runs, restore_runs, users, sessions)
