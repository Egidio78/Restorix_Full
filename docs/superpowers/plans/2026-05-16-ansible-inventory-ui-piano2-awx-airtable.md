# ansible-inventory-ui — Piano 2: AWX + Airtable Integration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrare il backend con AWX REST API v2 (gestione host negli inventory) e Airtable REST API v0 (sync bidirezionale), aggiungendo audit log API.

**Architecture:** Due client HTTP async (`awx_client.py`, `airtable_client.py`) iniettati come dipendenze FastAPI via `get_awx_client()` / `get_airtable_client()` aggiunti a `api/deps.py`. Il CRUD server esistente (`api/servers.py`) viene arricchito con chiamate AWX e auto-export Airtable. Se le credenziali non sono configurate in `.env`, le chiamate esterne vengono saltate silenziosamente. Nessuna nuova migration: lo schema del Piano 1 è già completo (`awx_host_id`, `airtable_record_id`, `audit_log`).

**Tech Stack:** Python 3.12, FastAPI 0.115, httpx 0.28 (client HTTP async), pyyaml 6.0 (YAML variabili AWX), respx 0.22 (mock httpx nei test)

---

## Struttura file

```
ansible-inventory-ui/backend/
├── integrations/
│   ├── __init__.py                  # nuovo (vuoto)
│   ├── awx_client.py                # nuovo — AWX REST API v2
│   └── airtable_client.py           # nuovo — Airtable REST API v0
├── api/
│   ├── deps.py                      # modifica — aggiunge get_awx_client, get_airtable_client
│   ├── awx.py                       # nuovo — GET /api/awx/inventories
│   ├── airtable.py                  # nuovo — import, conflitti (Admin)
│   ├── audit.py                     # nuovo — GET /api/admin/audit (Admin)
│   └── servers.py                   # modifica — AWX + Airtable + audit nel CRUD
├── tests/
│   ├── test_awx_client.py           # nuovo
│   ├── test_awx_api.py              # nuovo
│   ├── test_airtable_client.py      # nuovo
│   ├── test_airtable_api.py         # nuovo
│   └── test_audit.py                # nuovo
├── requirements.txt                 # modifica — aggiunge httpx, pyyaml
└── requirements-dev.txt             # modifica — aggiunge respx
```

---

### Task 1: Requirements + AWX Client

**Files:**
- Modify: `ansible-inventory-ui/backend/requirements.txt`
- Modify: `ansible-inventory-ui/backend/requirements-dev.txt`
- Create: `ansible-inventory-ui/backend/integrations/__init__.py`
- Create: `ansible-inventory-ui/backend/integrations/awx_client.py`
- Test: `ansible-inventory-ui/backend/tests/test_awx_client.py`

- [ ] **Step 1: Aggiorna `backend/requirements.txt`**

```
fastapi==0.115.5
uvicorn[standard]==0.32.1
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
alembic==1.14.0
pydantic-settings==2.6.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
bcrypt==4.0.1
pyotp==2.9.0
qrcode==7.4.2
python-multipart==0.0.17
httpx==0.28.0
pyyaml==6.0.2
```

- [ ] **Step 2: Aggiorna `backend/requirements-dev.txt`**

```
pytest==8.3.3
pytest-asyncio==0.24.0
pytest-cov==6.0.0
httpx==0.28.0
aiosqlite==0.20.0
respx==0.22.0
```

- [ ] **Step 3: Crea `backend/integrations/__init__.py`**

File vuoto.

- [ ] **Step 4: Scrivi il test fallente `backend/tests/test_awx_client.py`**

```python
import httpx
import respx
from integrations.awx_client import AWXClient, server_to_variables


@respx.mock
async def test_list_inventories():
    respx.get("http://awx.test/api/v2/inventories/").mock(
        return_value=httpx.Response(200, json={"results": [{"id": 1, "name": "Linux"}]})
    )
    client = AWXClient("http://awx.test", "tok")
    result = await client.list_inventories()
    assert result == [{"id": 1, "name": "Linux"}]


@respx.mock
async def test_check_host_exists_found():
    respx.get("http://awx.test/api/v2/hosts/").mock(
        return_value=httpx.Response(200, json={"results": [{"id": 42, "name": "srv-01"}]})
    )
    client = AWXClient("http://awx.test", "tok")
    result = await client.check_host_exists("srv-01", 1)
    assert result == {"id": 42, "name": "srv-01"}


@respx.mock
async def test_check_host_exists_not_found():
    respx.get("http://awx.test/api/v2/hosts/").mock(
        return_value=httpx.Response(200, json={"results": []})
    )
    client = AWXClient("http://awx.test", "tok")
    result = await client.check_host_exists("srv-99", 1)
    assert result is None


@respx.mock
async def test_create_host():
    respx.post("http://awx.test/api/v2/hosts/").mock(
        return_value=httpx.Response(201, json={"id": 10, "name": "srv-new"})
    )
    client = AWXClient("http://awx.test", "tok")
    result = await client.create_host(inventory_id=1, hostname="srv-new", variables="ambiente: Produzione\n")
    assert result["id"] == 10


@respx.mock
async def test_update_host():
    respx.patch("http://awx.test/api/v2/hosts/10/").mock(
        return_value=httpx.Response(200, json={"id": 10})
    )
    client = AWXClient("http://awx.test", "tok")
    result = await client.update_host(host_id=10, variables="ambiente: Staging\n")
    assert result["id"] == 10


@respx.mock
async def test_delete_host():
    respx.delete("http://awx.test/api/v2/hosts/10/").mock(
        return_value=httpx.Response(204)
    )
    client = AWXClient("http://awx.test", "tok")
    await client.delete_host(host_id=10)  # nessuna eccezione = ok


def test_server_to_variables():
    class FakeServer:
        ambiente = "Produzione"
        tipo_asset = "VPS"
        nome_cliente = "Acme"
        codice_cliente = "CL001"
        distribuzione_os = "Ubuntu Server"
        versione_os = "22.04 LTS"
        hypervisor = "Nessuno"
        cluster_hypervisor = None

    yaml_str = server_to_variables(FakeServer())
    assert "ambiente: Produzione" in yaml_str
    assert "tipo_asset: VPS" in yaml_str
    assert "cluster_hypervisor" not in yaml_str  # None escluso
```

- [ ] **Step 5: Esegui i test — verifica che falliscono**

```bash
cd ansible-inventory-ui/backend
$env:JWT_SECRET="test-secret-for-testing" ; pytest tests/test_awx_client.py -v
```

Expected: `FAILED ... ModuleNotFoundError: No module named 'integrations'`

- [ ] **Step 6: Crea `backend/integrations/awx_client.py`**

```python
import httpx
import yaml


class AWXClient:
    def __init__(self, base_url: str, token: str):
        self._base = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def list_inventories(self) -> list[dict]:
        async with httpx.AsyncClient(verify=False) as client:
            r = await client.get(f"{self._base}/api/v2/inventories/", headers=self._headers)
            r.raise_for_status()
            return r.json()["results"]

    async def check_host_exists(self, hostname: str, inventory_id: int) -> dict | None:
        async with httpx.AsyncClient(verify=False) as client:
            r = await client.get(
                f"{self._base}/api/v2/hosts/",
                params={"name": hostname, "inventory": inventory_id},
                headers=self._headers,
            )
            r.raise_for_status()
            results = r.json()["results"]
            return results[0] if results else None

    async def create_host(self, inventory_id: int, hostname: str, variables: str) -> dict:
        async with httpx.AsyncClient(verify=False) as client:
            r = await client.post(
                f"{self._base}/api/v2/hosts/",
                json={"name": hostname, "inventory": inventory_id, "variables": variables},
                headers=self._headers,
            )
            r.raise_for_status()
            return r.json()

    async def update_host(self, host_id: int, variables: str) -> dict:
        async with httpx.AsyncClient(verify=False) as client:
            r = await client.patch(
                f"{self._base}/api/v2/hosts/{host_id}/",
                json={"variables": variables},
                headers=self._headers,
            )
            r.raise_for_status()
            return r.json()

    async def delete_host(self, host_id: int) -> None:
        async with httpx.AsyncClient(verify=False) as client:
            r = await client.delete(
                f"{self._base}/api/v2/hosts/{host_id}/",
                headers=self._headers,
            )
            r.raise_for_status()


def server_to_variables(server) -> str:
    fields = [
        "ambiente", "tipo_asset", "nome_cliente", "codice_cliente",
        "distribuzione_os", "versione_os", "hypervisor", "cluster_hypervisor",
    ]
    data = {f: str(getattr(server, f)) for f in fields if getattr(server, f, None) is not None}
    return yaml.dump(data, allow_unicode=True, default_flow_style=False)
```

- [ ] **Step 7: Esegui i test — verifica che passano**

```bash
cd ansible-inventory-ui/backend
$env:JWT_SECRET="test-secret-for-testing" ; pytest tests/test_awx_client.py -v
```

Expected: `7 passed`

- [ ] **Step 8: Commit**

```bash
cd ansible-inventory-ui
git add backend/requirements.txt backend/requirements-dev.txt backend/integrations/ backend/tests/test_awx_client.py
git commit -m "feat: AWX client — list inventories, CRUD host, YAML variables"
```

---

### Task 2: Airtable Client

**Files:**
- Create: `ansible-inventory-ui/backend/integrations/airtable_client.py`
- Test: `ansible-inventory-ui/backend/tests/test_airtable_client.py`

- [ ] **Step 1: Scrivi il test fallente `backend/tests/test_airtable_client.py`**

```python
import httpx
import respx
from integrations.airtable_client import AirtableClient, FIELD_MAP


@respx.mock
async def test_list_records_single_page():
    respx.get("https://api.airtable.com/v0/appTEST/Servers").mock(
        return_value=httpx.Response(200, json={
            "records": [{"id": "recABC", "fields": {"Hostname": "srv-01"}}]
        })
    )
    client = AirtableClient("tok", "appTEST", "Servers")
    records = await client.list_records()
    assert len(records) == 1
    assert records[0]["id"] == "recABC"


@respx.mock
async def test_list_records_pagination():
    respx.get("https://api.airtable.com/v0/appTEST/Servers").mock(side_effect=[
        httpx.Response(200, json={
            "records": [{"id": "rec1", "fields": {}}],
            "offset": "page2token",
        }),
        httpx.Response(200, json={
            "records": [{"id": "rec2", "fields": {}}],
        }),
    ])
    client = AirtableClient("tok", "appTEST", "Servers")
    records = await client.list_records()
    assert len(records) == 2


@respx.mock
async def test_create_record():
    respx.post("https://api.airtable.com/v0/appTEST/Servers").mock(
        return_value=httpx.Response(200, json={"id": "recNEW", "fields": {"Hostname": "srv-02"}})
    )
    client = AirtableClient("tok", "appTEST", "Servers")
    result = await client.create_record({"Hostname": "srv-02"})
    assert result["id"] == "recNEW"


@respx.mock
async def test_update_record():
    respx.patch("https://api.airtable.com/v0/appTEST/Servers/recABC").mock(
        return_value=httpx.Response(200, json={"id": "recABC"})
    )
    client = AirtableClient("tok", "appTEST", "Servers")
    result = await client.update_record("recABC", {"Hostname": "srv-01-upd"})
    assert result["id"] == "recABC"


def test_server_to_fields():
    class FakeServer:
        hostname = "srv-01"
        fqdn = None
        ip = "10.0.0.1"
        nome_cliente = "Acme"
        codice_cliente = "CL001"
        ambiente = "Produzione"
        tipo_asset = "VPS"
        sistema_operativo = "Linux"
        distribuzione_os = "Ubuntu Server"
        versione_os = "22.04 LTS"
        hypervisor = "Nessuno"
        cluster_hypervisor = None

    client = AirtableClient("tok", "appTEST", "Servers")
    fields = client.server_to_fields(FakeServer())
    assert fields["Hostname"] == "srv-01"
    assert fields["IP"] == "10.0.0.1"
    assert fields["Nome Cliente"] == "Acme"
    assert "FQDN" not in fields
    assert "Cluster Hypervisor" not in fields


def test_fields_to_server():
    client = AirtableClient("tok", "appTEST", "Servers")
    fields = {"Hostname": "srv-01", "IP": "10.0.0.1", "Nome Cliente": "Acme"}
    result = client.fields_to_server(fields)
    assert result["hostname"] == "srv-01"
    assert result["ip"] == "10.0.0.1"
    assert result["nome_cliente"] == "Acme"
```

- [ ] **Step 2: Esegui i test — verifica che falliscono**

```bash
cd ansible-inventory-ui/backend
$env:JWT_SECRET="test-secret-for-testing" ; pytest tests/test_airtable_client.py -v
```

Expected: `FAILED ... ModuleNotFoundError`

- [ ] **Step 3: Crea `backend/integrations/airtable_client.py`**

```python
import httpx

AIRTABLE_API_BASE = "https://api.airtable.com/v0"

FIELD_MAP: dict[str, str] = {
    "hostname": "Hostname",
    "fqdn": "FQDN",
    "ip": "IP",
    "nome_cliente": "Nome Cliente",
    "codice_cliente": "Codice Cliente",
    "ambiente": "Ambiente",
    "tipo_asset": "Tipo Asset",
    "sistema_operativo": "Sistema Operativo",
    "distribuzione_os": "Distribuzione OS",
    "versione_os": "Versione OS",
    "hypervisor": "Hypervisor",
    "cluster_hypervisor": "Cluster Hypervisor",
}


class AirtableClient:
    def __init__(self, api_token: str, base_id: str, table_name: str):
        self._base_id = base_id
        self._table = table_name
        self._headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    def _url(self) -> str:
        return f"{AIRTABLE_API_BASE}/{self._base_id}/{self._table}"

    def server_to_fields(self, server) -> dict:
        fields: dict = {}
        for db_field, at_field in FIELD_MAP.items():
            val = getattr(server, db_field, None)
            if val is not None:
                fields[at_field] = str(val)
        return fields

    def fields_to_server(self, fields: dict) -> dict:
        reverse: dict[str, str] = {v: k for k, v in FIELD_MAP.items()}
        return {reverse[k]: v for k, v in fields.items() if k in reverse}

    async def list_records(self) -> list[dict]:
        records: list[dict] = []
        params: dict = {}
        async with httpx.AsyncClient() as client:
            while True:
                r = await client.get(self._url(), headers=self._headers, params=params)
                r.raise_for_status()
                data = r.json()
                records.extend(data.get("records", []))
                offset = data.get("offset")
                if not offset:
                    break
                params = {"offset": offset}
        return records

    async def create_record(self, fields: dict) -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.post(self._url(), headers=self._headers, json={"fields": fields})
            r.raise_for_status()
            return r.json()

    async def update_record(self, record_id: str, fields: dict) -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.patch(
                f"{self._url()}/{record_id}",
                headers=self._headers,
                json={"fields": fields},
            )
            r.raise_for_status()
            return r.json()
```

- [ ] **Step 4: Esegui i test — verifica che passano**

```bash
cd ansible-inventory-ui/backend
$env:JWT_SECRET="test-secret-for-testing" ; pytest tests/test_airtable_client.py -v
```

Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
cd ansible-inventory-ui
git add backend/integrations/airtable_client.py backend/tests/test_airtable_client.py
git commit -m "feat: Airtable client — list, create, update, field mapping"
```

---

### Task 3: AWX inventories endpoint + dipendenze client

**Files:**
- Modify: `ansible-inventory-ui/backend/api/deps.py`
- Create: `ansible-inventory-ui/backend/api/awx.py`
- Modify: `ansible-inventory-ui/backend/main.py`
- Test: `ansible-inventory-ui/backend/tests/test_awx_api.py`

- [ ] **Step 1: Scrivi il test fallente `backend/tests/test_awx_api.py`**

```python
from unittest.mock import AsyncMock, patch
from models.user import User, UserRole
from core.security import hash_password


async def _create_editor(db):
    user = User(
        username="editor", email="editor@example.com",
        hashed_password=hash_password("pass"),
        role=UserRole.editor, is_active=True,
    )
    db.add(user)
    await db.commit()


async def _get_token(client):
    resp = await client.post("/api/auth/login", json={"username": "editor", "password": "pass"})
    return resp.json()["access_token"]


async def test_list_inventories_awx_not_configured(client, db_session):
    await _create_editor(db_session)
    token = await _get_token(client)
    resp = await client.get("/api/awx/inventories", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 503
    assert "non configurato" in resp.json()["detail"]


async def test_list_inventories_awx_configured(client, db_session):
    await _create_editor(db_session)
    token = await _get_token(client)
    mock_awx = AsyncMock()
    mock_awx.list_inventories.return_value = [{"id": 1, "name": "Linux Servers"}]
    with patch("api.awx.get_awx_client", return_value=mock_awx):
        resp = await client.get("/api/awx/inventories", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == [{"id": 1, "name": "Linux Servers"}]
```

- [ ] **Step 2: Esegui il test — verifica che fallisce**

```bash
cd ansible-inventory-ui/backend
$env:JWT_SECRET="test-secret-for-testing" ; pytest tests/test_awx_api.py -v
```

Expected: `FAILED ... 404 Not Found`

- [ ] **Step 3: Modifica `backend/api/deps.py`** — aggiungi getter client in fondo

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError
from config import settings
from database import get_db
from models.user import User, UserRole
from core.security import decode_access_token
from integrations.awx_client import AWXClient
from integrations.airtable_client import AirtableClient

bearer = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token non valido")
    if payload.get("type") == "pre_auth":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token non valido")
    username: str = payload.get("sub", "")
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utente non trovato")
    return user


def require_role(*roles: UserRole):
    async def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permessi insufficienti")
        return current_user
    return checker


def get_awx_client() -> AWXClient | None:
    if not settings.awx_url or not settings.awx_token:
        return None
    return AWXClient(settings.awx_url, settings.awx_token)


def get_airtable_client() -> AirtableClient | None:
    if not settings.airtable_api_token or not settings.airtable_base_id:
        return None
    return AirtableClient(
        settings.airtable_api_token,
        settings.airtable_base_id,
        settings.airtable_table_name,
    )
```

- [ ] **Step 4: Crea `backend/api/awx.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from api.deps import get_current_user, get_awx_client
from integrations.awx_client import AWXClient
from models.user import User

router = APIRouter(prefix="/api/awx", tags=["awx"])


@router.get("/inventories")
async def list_inventories(
    _: User = Depends(get_current_user),
    awx: AWXClient | None = Depends(get_awx_client),
):
    if not awx:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="AWX non configurato")
    return await awx.list_inventories()
```

- [ ] **Step 5: Aggiorna `backend/main.py`**

```python
from fastapi import FastAPI
from api.auth import router as auth_router
from api.users import router as users_router
from api.servers import router as servers_router
from api.awx import router as awx_router

app = FastAPI(title="ansible-inventory-ui", version="1.0.0")

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(servers_router)
app.include_router(awx_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Esegui i test — verifica che passano**

```bash
cd ansible-inventory-ui/backend
$env:JWT_SECRET="test-secret-for-testing" ; pytest tests/test_awx_api.py tests/ -v --tb=short
```

Expected: `2 passed` per i nuovi, tutti i precedenti ancora verdi.

- [ ] **Step 7: Commit**

```bash
cd ansible-inventory-ui
git add backend/api/deps.py backend/api/awx.py backend/main.py backend/tests/test_awx_api.py
git commit -m "feat: AWX inventories endpoint + dependency injection client"
```

---

### Task 4: Integrazione AWX nel server CRUD

Modifica `api/servers.py` per chiamare AWX su create/update/delete e fare il Level 2 duplicate check.

**Files:**
- Modify: `ansible-inventory-ui/backend/api/servers.py`
- Modify: `ansible-inventory-ui/backend/tests/test_servers.py`

- [ ] **Step 1: Aggiungi test AWX in fondo a `backend/tests/test_servers.py`**

```python
from unittest.mock import AsyncMock, patch


async def test_create_server_calls_awx(client, db_session):
    await _create_user(db_session, UserRole.editor)
    token = await _get_token(client)
    mock_awx = AsyncMock()
    mock_awx.check_host_exists.return_value = None
    mock_awx.create_host.return_value = {"id": 99}
    with patch("api.servers.get_awx_client", return_value=mock_awx):
        payload = {**SERVER_PAYLOAD, "awx_inventory_id": 1}
        resp = await client.post("/api/servers/", json=payload,
                                  headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    assert resp.json()["awx_host_id"] == 99
    mock_awx.create_host.assert_called_once()


async def test_create_server_awx_level2_duplicate(client, db_session):
    await _create_user(db_session, UserRole.editor)
    token = await _get_token(client)
    mock_awx = AsyncMock()
    mock_awx.check_host_exists.return_value = {"id": 5, "name": "srv-test-01"}
    with patch("api.servers.get_awx_client", return_value=mock_awx):
        payload = {**SERVER_PAYLOAD, "awx_inventory_id": 1}
        resp = await client.post("/api/servers/", json=payload,
                                  headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 409
    assert "AWX" in resp.json()["detail"]


async def test_update_server_calls_awx(client, db_session):
    await _create_user(db_session, UserRole.editor)
    token = await _get_token(client)
    create = await client.post("/api/servers/", json=SERVER_PAYLOAD,
                                headers={"Authorization": f"Bearer {token}"})
    server_id = create.json()["id"]
    mock_awx = AsyncMock()
    mock_awx.update_host.return_value = {"id": 77}
    with patch("api.servers.get_awx_client", return_value=mock_awx):
        await client.patch(
            f"/api/servers/{server_id}",
            json={"awx_host_id": 77, "versione_os": "24.04 LTS"},
            headers={"Authorization": f"Bearer {token}"},
        )
    mock_awx.update_host.assert_called_once()


async def test_delete_server_calls_awx(client, db_session):
    admin = User(
        username="admin2", email="admin2@example.com",
        hashed_password=hash_password("adminpass"),
        role=UserRole.admin, is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()
    token = await _get_token(client, "admin2", "adminpass")
    create = await client.post("/api/servers/", json=SERVER_PAYLOAD,
                                headers={"Authorization": f"Bearer {token}"})
    server_id = create.json()["id"]
    mock_awx = AsyncMock()
    with patch("api.servers.get_awx_client", return_value=mock_awx):
        await client.patch(
            f"/api/servers/{server_id}",
            json={"awx_host_id": 55},
            headers={"Authorization": f"Bearer {token}"},
        )
        resp = await client.delete(f"/api/servers/{server_id}",
                                    headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 204
    mock_awx.delete_host.assert_called_once_with(host_id=55)
```

- [ ] **Step 2: Esegui i nuovi test — verifica che falliscono**

```bash
cd ansible-inventory-ui/backend
$env:JWT_SECRET="test-secret-for-testing" ; pytest tests/test_servers.py::test_create_server_calls_awx -v
```

Expected: `FAILED`

- [ ] **Step 3: Riscrivi `backend/api/servers.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models.server import Server, Ambiente, TipoAsset, SistemaOperativo, Hypervisor
from models.user import User, UserRole
from api.deps import get_current_user, require_role, get_awx_client, get_airtable_client
from integrations.awx_client import AWXClient, server_to_variables
from integrations.airtable_client import AirtableClient

router = APIRouter(prefix="/api/servers", tags=["servers"])
_viewer_plus = require_role(UserRole.viewer, UserRole.editor, UserRole.admin)
_editor_plus = require_role(UserRole.editor, UserRole.admin)
_admin_only = require_role(UserRole.admin)


class ServerCreate(BaseModel):
    hostname: str
    fqdn: str | None = None
    ip: str
    nome_cliente: str | None = None
    codice_cliente: str | None = None
    ambiente: Ambiente | None = None
    tipo_asset: TipoAsset | None = None
    sistema_operativo: SistemaOperativo | None = None
    distribuzione_os: str | None = None
    versione_os: str | None = None
    hypervisor: Hypervisor | None = None
    cluster_hypervisor: str | None = None
    awx_inventory_id: int | None = None


class ServerUpdate(BaseModel):
    fqdn: str | None = None
    ip: str | None = None
    nome_cliente: str | None = None
    codice_cliente: str | None = None
    ambiente: Ambiente | None = None
    tipo_asset: TipoAsset | None = None
    sistema_operativo: SistemaOperativo | None = None
    distribuzione_os: str | None = None
    versione_os: str | None = None
    hypervisor: Hypervisor | None = None
    cluster_hypervisor: str | None = None
    awx_inventory_id: int | None = None
    awx_host_id: int | None = None
    airtable_record_id: str | None = None


def _server_out(s: Server) -> dict:
    return {
        "id": s.id, "hostname": s.hostname, "fqdn": s.fqdn, "ip": s.ip,
        "nome_cliente": s.nome_cliente, "codice_cliente": s.codice_cliente,
        "ambiente": s.ambiente, "tipo_asset": s.tipo_asset,
        "sistema_operativo": s.sistema_operativo, "distribuzione_os": s.distribuzione_os,
        "versione_os": s.versione_os, "hypervisor": s.hypervisor,
        "cluster_hypervisor": s.cluster_hypervisor,
        "awx_inventory_id": s.awx_inventory_id, "awx_host_id": s.awx_host_id,
        "airtable_record_id": s.airtable_record_id,
        "created_by": s.created_by, "created_at": s.created_at, "updated_at": s.updated_at,
    }


@router.get("/check-duplicate")
async def check_duplicate(
    hostname: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_viewer_plus),
):
    result = await db.execute(select(Server).where(Server.hostname == hostname))
    existing = result.scalar_one_or_none()
    if existing:
        return {"available": False, "existing": _server_out(existing)}
    return {"available": True}


@router.get("/")
async def list_servers(
    nome_cliente: str | None = None,
    sistema_operativo: str | None = None,
    awx_inventory_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_viewer_plus),
):
    query = select(Server)
    if nome_cliente:
        query = query.where(Server.nome_cliente == nome_cliente)
    if sistema_operativo:
        query = query.where(Server.sistema_operativo == sistema_operativo)
    if awx_inventory_id:
        query = query.where(Server.awx_inventory_id == awx_inventory_id)
    result = await db.execute(query)
    return [_server_out(s) for s in result.scalars().all()]


@router.post("/", status_code=201)
async def create_server(
    body: ServerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_editor_plus),
    awx: AWXClient | None = Depends(get_awx_client),
    airtable: AirtableClient | None = Depends(get_airtable_client),
):
    existing = await db.execute(select(Server).where(Server.hostname == body.hostname))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Hostname '{body.hostname}' già presente")

    if awx and body.awx_inventory_id:
        awx_existing = await awx.check_host_exists(body.hostname, body.awx_inventory_id)
        if awx_existing:
            raise HTTPException(
                status_code=409,
                detail=f"Hostname '{body.hostname}' già presente in AWX (host_id={awx_existing['id']})",
            )

    server = Server(**body.model_dump(), created_by=current_user.id)
    db.add(server)
    await db.flush()

    if awx and server.awx_inventory_id:
        awx_host = await awx.create_host(
            inventory_id=server.awx_inventory_id,
            hostname=server.hostname,
            variables=server_to_variables(server),
        )
        server.awx_host_id = awx_host["id"]

    if airtable:
        at_record = await airtable.create_record(airtable.server_to_fields(server))
        server.airtable_record_id = at_record["id"]

    await db.commit()
    await db.refresh(server)
    return _server_out(server)


@router.patch("/{server_id}")
async def update_server(
    server_id: int,
    body: ServerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_editor_plus),
    awx: AWXClient | None = Depends(get_awx_client),
    airtable: AirtableClient | None = Depends(get_airtable_client),
):
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server non trovato")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(server, field, value)

    if awx and server.awx_host_id:
        await awx.update_host(host_id=server.awx_host_id, variables=server_to_variables(server))

    if airtable:
        at_fields = airtable.server_to_fields(server)
        if server.airtable_record_id:
            await airtable.update_record(server.airtable_record_id, at_fields)
        else:
            at_record = await airtable.create_record(at_fields)
            server.airtable_record_id = at_record["id"]

    await db.commit()
    await db.refresh(server)
    return _server_out(server)


@router.delete("/{server_id}", status_code=204)
async def delete_server(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_admin_only),
    awx: AWXClient | None = Depends(get_awx_client),
):
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server non trovato")

    if awx and server.awx_host_id:
        await awx.delete_host(host_id=server.awx_host_id)

    await db.delete(server)
    await db.commit()
```

- [ ] **Step 4: Esegui tutta la suite**

```bash
cd ansible-inventory-ui/backend
$env:JWT_SECRET="test-secret-for-testing" ; pytest tests/ -v --tb=short
```

Expected: tutti i test verdi (inclusi i 4 nuovi AWX).

- [ ] **Step 5: Commit**

```bash
cd ansible-inventory-ui
git add backend/api/servers.py backend/tests/test_servers.py
git commit -m "feat: integra AWX nel server CRUD — create/update/delete/level2-duplicate"
```

---

### Task 5: Airtable API (import, conflitti, risoluzione)

**Files:**
- Create: `ansible-inventory-ui/backend/api/airtable.py`
- Modify: `ansible-inventory-ui/backend/main.py`
- Test: `ansible-inventory-ui/backend/tests/test_airtable_api.py`

- [ ] **Step 1: Scrivi il test fallente `backend/tests/test_airtable_api.py`**

```python
from unittest.mock import AsyncMock, patch
from models.user import User, UserRole
from models.server import Server
from core.security import hash_password


async def _create_admin(db):
    user = User(
        username="admin", email="admin@example.com",
        hashed_password=hash_password("adminpass"),
        role=UserRole.admin, is_active=True,
    )
    db.add(user)
    await db.commit()
    return user


async def _get_token(client):
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    return resp.json()["access_token"]


async def test_import_not_configured(client, db_session):
    await _create_admin(db_session)
    token = await _get_token(client)
    resp = await client.post("/api/airtable/import", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 503


async def test_import_creates_new_servers(client, db_session):
    admin = await _create_admin(db_session)
    token = await _get_token(client)
    mock_at = AsyncMock()
    mock_at.list_records.return_value = [
        {"id": "recABC", "fields": {"Hostname": "srv-imported", "IP": "10.0.0.5"}},
    ]
    mock_at.fields_to_server.return_value = {"hostname": "srv-imported", "ip": "10.0.0.5"}
    with patch("api.airtable.get_airtable_client", return_value=mock_at):
        resp = await client.post("/api/airtable/import", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["created"] == 1
    assert resp.json()["conflicts"] == 0


async def test_get_conflicts_not_configured(client, db_session):
    await _create_admin(db_session)
    token = await _get_token(client)
    resp = await client.get("/api/airtable/conflicts", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 503


async def test_get_conflicts_returns_diffs(client, db_session):
    admin = await _create_admin(db_session)
    token = await _get_token(client)
    server = Server(
        hostname="srv-01", ip="10.0.0.1",
        versione_os="22.04 LTS", airtable_record_id="recABC",
        created_by=admin.id,
    )
    db_session.add(server)
    await db_session.commit()

    mock_at = AsyncMock()
    mock_at.list_records.return_value = [
        {"id": "recABC", "fields": {"Hostname": "srv-01", "IP": "10.0.0.1", "Versione OS": "20.04 LTS"}},
    ]
    with patch("api.airtable.get_airtable_client", return_value=mock_at):
        resp = await client.get("/api/airtable/conflicts", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    conflicts = resp.json()
    assert len(conflicts) == 1
    diffs = {d["field"]: d for d in conflicts[0]["diffs"]}
    assert "versione_os" in diffs
    assert diffs["versione_os"]["db_value"] == "22.04 LTS"
    assert diffs["versione_os"]["airtable_value"] == "20.04 LTS"


async def test_resolve_db_wins(client, db_session):
    admin = await _create_admin(db_session)
    token = await _get_token(client)
    server = Server(
        hostname="srv-01", ip="10.0.0.1", airtable_record_id="recABC",
        created_by=admin.id,
    )
    db_session.add(server)
    await db_session.commit()

    mock_at = AsyncMock()
    mock_at.server_to_fields.return_value = {"Hostname": "srv-01"}
    mock_at.update_record.return_value = {"id": "recABC"}
    with patch("api.airtable.get_airtable_client", return_value=mock_at):
        resp = await client.post(
            "/api/airtable/conflicts/resolve",
            json={"server_id": server.id, "source": "db"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    mock_at.update_record.assert_called_once()


async def test_resolve_airtable_wins(client, db_session):
    admin = await _create_admin(db_session)
    token = await _get_token(client)
    server = Server(
        hostname="srv-01", ip="10.0.0.1",
        versione_os="22.04 LTS", airtable_record_id="recABC",
        created_by=admin.id,
    )
    db_session.add(server)
    await db_session.commit()

    mock_at = AsyncMock()
    mock_at.list_records.return_value = [
        {"id": "recABC", "fields": {"Hostname": "srv-01", "IP": "10.0.0.1", "Versione OS": "20.04 LTS"}},
    ]
    mock_at.fields_to_server.return_value = {"versione_os": "20.04 LTS"}
    with patch("api.airtable.get_airtable_client", return_value=mock_at):
        resp = await client.post(
            "/api/airtable/conflicts/resolve",
            json={"server_id": server.id, "source": "airtable"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["versione_os"] == "20.04 LTS"
```

- [ ] **Step 2: Esegui i test — verifica che falliscono**

```bash
cd ansible-inventory-ui/backend
$env:JWT_SECRET="test-secret-for-testing" ; pytest tests/test_airtable_api.py -v
```

Expected: `FAILED ... 404 Not Found`

- [ ] **Step 3: Crea `backend/api/airtable.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models.server import Server
from models.user import User, UserRole
from api.deps import require_role, get_airtable_client
from integrations.airtable_client import AirtableClient, FIELD_MAP

router = APIRouter(prefix="/api/airtable", tags=["airtable"])
_admin = require_role(UserRole.admin)


class ResolveRequest(BaseModel):
    server_id: int
    source: str  # "db" | "airtable"


@router.post("/import")
async def import_from_airtable(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_admin),
    airtable: AirtableClient | None = Depends(get_airtable_client),
):
    if not airtable:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Airtable non configurato")

    records = await airtable.list_records()
    created = updated = conflicts = 0

    for record in records:
        record_id = record["id"]
        fields = record.get("fields", {})
        server_data = airtable.fields_to_server(fields)
        hostname = server_data.get("hostname")
        if not hostname:
            continue

        result = await db.execute(select(Server).where(Server.airtable_record_id == record_id))
        existing = result.scalar_one_or_none()

        if existing:
            has_diff = any(
                str(getattr(existing, k, "") or "") != str(v or "")
                for k, v in server_data.items()
                if k != "hostname"
            )
            if has_diff:
                conflicts += 1
            else:
                updated += 1
        else:
            result2 = await db.execute(select(Server).where(Server.hostname == hostname))
            by_hostname = result2.scalar_one_or_none()
            if by_hostname:
                by_hostname.airtable_record_id = record_id
                updated += 1
            else:
                db.add(Server(**server_data, airtable_record_id=record_id))
                created += 1

    await db.commit()
    return {"created": created, "updated": updated, "conflicts": conflicts}


@router.get("/conflicts")
async def get_conflicts(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_admin),
    airtable: AirtableClient | None = Depends(get_airtable_client),
):
    if not airtable:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Airtable non configurato")

    records = await airtable.list_records()
    at_by_id = {r["id"]: r["fields"] for r in records}

    result = await db.execute(select(Server).where(Server.airtable_record_id.isnot(None)))
    servers = result.scalars().all()

    reverse_map = {v: k for k, v in FIELD_MAP.items()}
    conflicts = []
    for server in servers:
        at_fields = at_by_id.get(server.airtable_record_id)
        if not at_fields:
            continue
        diffs = []
        for at_field, db_field in reverse_map.items():
            db_val = str(getattr(server, db_field, "") or "")
            at_val = str(at_fields.get(at_field, "") or "")
            if db_val != at_val:
                diffs.append({"field": db_field, "db_value": db_val or None, "airtable_value": at_val or None})
        if diffs:
            conflicts.append({
                "server_id": server.id,
                "hostname": server.hostname,
                "airtable_record_id": server.airtable_record_id,
                "diffs": diffs,
            })
    return conflicts


@router.post("/conflicts/resolve")
async def resolve_conflict(
    body: ResolveRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_admin),
    airtable: AirtableClient | None = Depends(get_airtable_client),
):
    if not airtable:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Airtable non configurato")
    if body.source not in ("db", "airtable"):
        raise HTTPException(status_code=400, detail="source deve essere 'db' o 'airtable'")

    result = await db.execute(select(Server).where(Server.id == body.server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server non trovato")

    if body.source == "db":
        await airtable.update_record(server.airtable_record_id, airtable.server_to_fields(server))
        return {"status": "ok", "source": "db"}

    records = await airtable.list_records()
    at_record = next((r for r in records if r["id"] == server.airtable_record_id), None)
    if not at_record:
        raise HTTPException(status_code=404, detail="Record Airtable non trovato")
    server_data = airtable.fields_to_server(at_record["fields"])
    for field, value in server_data.items():
        if field != "hostname":
            setattr(server, field, value)
    await db.commit()
    await db.refresh(server)
    return {"status": "ok", "source": "airtable", **{k: getattr(server, k) for k in server_data if k != "hostname"}}
```

- [ ] **Step 4: Aggiorna `backend/main.py`**

```python
from fastapi import FastAPI
from api.auth import router as auth_router
from api.users import router as users_router
from api.servers import router as servers_router
from api.awx import router as awx_router
from api.airtable import router as airtable_router

app = FastAPI(title="ansible-inventory-ui", version="1.0.0")

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(servers_router)
app.include_router(awx_router)
app.include_router(airtable_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Esegui tutta la suite**

```bash
cd ansible-inventory-ui/backend
$env:JWT_SECRET="test-secret-for-testing" ; pytest tests/ -v --tb=short
```

Expected: tutti i test verdi.

- [ ] **Step 6: Commit**

```bash
cd ansible-inventory-ui
git add backend/api/airtable.py backend/main.py backend/tests/test_airtable_api.py
git commit -m "feat: Airtable API — import, conflict detection, conflict resolution"
```

---

### Task 6: Audit Log API + logging su create/update/delete

**Files:**
- Create: `ansible-inventory-ui/backend/api/audit.py`
- Modify: `ansible-inventory-ui/backend/api/servers.py`
- Modify: `ansible-inventory-ui/backend/main.py`
- Test: `ansible-inventory-ui/backend/tests/test_audit.py`

- [ ] **Step 1: Scrivi il test fallente `backend/tests/test_audit.py`**

```python
from models.user import User, UserRole
from core.security import hash_password

SERVER_PAYLOAD = {
    "hostname": "srv-audit-01", "ip": "192.168.1.99",
    "ambiente": "Test", "tipo_asset": "VPS",
    "sistema_operativo": "Linux", "hypervisor": "Nessuno",
}


async def _create_admin(db):
    user = User(
        username="admin", email="admin@example.com",
        hashed_password=hash_password("adminpass"),
        role=UserRole.admin, is_active=True,
    )
    db.add(user)
    await db.commit()
    return user


async def _get_token(client):
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    return resp.json()["access_token"]


async def test_audit_log_after_create(client, db_session):
    await _create_admin(db_session)
    token = await _get_token(client)
    await client.post("/api/servers/", json=SERVER_PAYLOAD,
                      headers={"Authorization": f"Bearer {token}"})
    resp = await client.get("/api/admin/audit", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    logs = resp.json()
    assert any(l["action"] == "create" and l["server_hostname"] == "srv-audit-01" for l in logs)


async def test_audit_log_after_delete(client, db_session):
    await _create_admin(db_session)
    token = await _get_token(client)
    create = await client.post("/api/servers/", json=SERVER_PAYLOAD,
                                headers={"Authorization": f"Bearer {token}"})
    server_id = create.json()["id"]
    await client.delete(f"/api/servers/{server_id}", headers={"Authorization": f"Bearer {token}"})
    resp = await client.get("/api/admin/audit", headers={"Authorization": f"Bearer {token}"})
    logs = resp.json()
    assert any(l["action"] == "delete" and l["server_hostname"] == "srv-audit-01" for l in logs)


async def test_viewer_cannot_access_audit(client, db_session):
    viewer = User(
        username="viewer", email="viewer@example.com",
        hashed_password=hash_password("pass"),
        role=UserRole.viewer, is_active=True,
    )
    db_session.add(viewer)
    await db_session.commit()
    resp_login = await client.post("/api/auth/login", json={"username": "viewer", "password": "pass"})
    token = resp_login.json()["access_token"]
    resp = await client.get("/api/admin/audit", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
```

- [ ] **Step 2: Esegui i test — verifica che falliscono**

```bash
cd ansible-inventory-ui/backend
$env:JWT_SECRET="test-secret-for-testing" ; pytest tests/test_audit.py -v
```

Expected: `FAILED ... 404 Not Found`

- [ ] **Step 3: Crea `backend/api/audit.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models.audit import AuditLog
from models.user import User, UserRole
from api.deps import require_role

router = APIRouter(prefix="/api/admin", tags=["audit"])
_admin = require_role(UserRole.admin)


@router.get("/audit")
async def list_audit_log(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_admin),
):
    result = await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()))
    logs = result.scalars().all()
    return [
        {
            "id": l.id,
            "user_id": l.user_id,
            "action": l.action,
            "server_hostname": l.server_hostname,
            "detail": l.detail,
            "created_at": l.created_at,
        }
        for l in logs
    ]
```

- [ ] **Step 4: Aggiungi audit logging in `backend/api/servers.py`**

Aggiungi questi import in cima al file (dopo gli import esistenti):

```python
import json
from models.audit import AuditLog
```

Aggiungi il helper prima di `_server_out`:

```python
async def _audit(db: AsyncSession, user_id: int | None, action: str, hostname: str, detail: dict) -> None:
    db.add(AuditLog(
        user_id=user_id,
        action=action,
        server_hostname=hostname,
        detail=json.dumps(detail, default=str),
    ))
```

In `create_server`, prima di `await db.commit()` aggiungi:

```python
    await _audit(db, current_user.id, "create", server.hostname, {"ip": server.ip})
```

In `update_server`, prima di `await db.commit()` aggiungi:

```python
    await _audit(db, current_user.id, "update", server.hostname, body.model_dump(exclude_none=True))
```

In `delete_server`, prima di `await db.delete(server)` aggiungi:

```python
    await _audit(db, current_user.id, "delete", server.hostname, {})
```

- [ ] **Step 5: Aggiorna `backend/main.py`**

```python
from fastapi import FastAPI
from api.auth import router as auth_router
from api.users import router as users_router
from api.servers import router as servers_router
from api.awx import router as awx_router
from api.airtable import router as airtable_router
from api.audit import router as audit_router

app = FastAPI(title="ansible-inventory-ui", version="1.0.0")

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(servers_router)
app.include_router(awx_router)
app.include_router(airtable_router)
app.include_router(audit_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Esegui tutta la suite**

```bash
cd ansible-inventory-ui/backend
$env:JWT_SECRET="test-secret-for-testing" ; pytest tests/ -v --tb=short
```

Expected: tutti i test verdi.

- [ ] **Step 7: Commit**

```bash
cd ansible-inventory-ui
git add backend/api/audit.py backend/api/servers.py backend/main.py backend/tests/test_audit.py
git commit -m "feat: audit log API + logging su create/update/delete server"
```

---

## Self-Review — Copertura Spec (Piano 2)

| Requisito spec | Task |
|---|---|
| Lista inventory AWX (Step 1 wizard) | Task 3 |
| Verifica duplicato via AWX al submit (Level 2) | Task 4 |
| Aggiungi host AWX | Task 4 |
| Aggiorna host AWX | Task 4 |
| Elimina host AWX | Task 4 |
| Export → Airtable automatico su create/update | Task 4 |
| Import ← Airtable manuale (Admin) | Task 5 |
| Risoluzione conflitti DB vs Airtable (Admin) | Task 5 |
| Audit log API (Admin) | Task 6 |
| Audit logging su create/update/delete server | Task 6 |

**Rinviato a Piano 3:**
- Frontend Next.js (wizard 4-step, login con TOTP, dashboard, admin UI)
