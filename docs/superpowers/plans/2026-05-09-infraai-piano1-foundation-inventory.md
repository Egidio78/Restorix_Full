# InfraAI — Piano 1: Foundation + Inventory

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Costruire il layer fondazionale: infrastruttura Docker Compose, schema PostgreSQL, e il sistema di inventario che importa server da Zabbix (Windows), RDM CSV (Linux) e Uptime Kuma (servizi web).

**Architecture:** Backend FastAPI con SQLAlchemy 2.0 e tre client async per le sorgenti dati esterne (Zabbix, Kuma, RDM). Un sync orchestrator unifica tutto in un database PostgreSQL locale. Nessuna UI in questo piano — solo API REST e logica testata.

**Tech Stack:** Python 3.12, FastAPI 0.115, SQLAlchemy 2.0 + asyncpg, Alembic, httpx, respx, pytest + pytest-asyncio, Docker Compose, PostgreSQL 16, Nginx

---

## Struttura file

```
infraai/
├── backend/
│   ├── main.py                      # FastAPI app + router registration
│   ├── config.py                    # Settings via pydantic-settings
│   ├── database.py                  # Async SQLAlchemy engine + session
│   ├── pytest.ini                   # Test configuration + PYTHONPATH
│   ├── models/
│   │   ├── __init__.py              # Re-export all models
│   │   ├── server.py                # Server inventory model
│   │   └── audit.py                 # CommandHistory model
│   ├── inventory/
│   │   ├── __init__.py
│   │   ├── zabbix_client.py         # Async Zabbix JSON-RPC client
│   │   ├── kuma_client.py           # Async Uptime Kuma REST client
│   │   ├── rdm_importer.py          # RDM CSV parser + DB upsert
│   │   └── sync.py                  # Sync orchestrator (tutte le sorgenti)
│   ├── api/
│   │   ├── __init__.py
│   │   └── inventory.py             # Endpoints: list, import CSV, sync
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py              # Fixture: DB in-memory, sessione
│       ├── test_zabbix_client.py
│       ├── test_kuma_client.py
│       ├── test_rdm_importer.py
│       └── test_sync.py
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
└── nginx/
    ├── nginx.conf
    └── whitelist.conf
```

---

### Task 1: Project Foundation

**Files:**
- Create: `infraai/backend/requirements.txt`
- Create: `infraai/backend/requirements-dev.txt`
- Create: `infraai/.env.example`
- Create: `infraai/backend/config.py`
- Create: `infraai/backend/database.py`
- Create: `infraai/backend/main.py`
- Create: `infraai/backend/Dockerfile`
- Create: `infraai/backend/pytest.ini`
- Create: `infraai/docker-compose.yml`
- Create: directory vuote con `__init__.py`

- [ ] **Step 1: Crea la struttura di directory**

```bash
mkdir -p infraai/backend/models infraai/backend/inventory infraai/backend/api infraai/backend/tests infraai/nginx
touch infraai/backend/models/__init__.py
touch infraai/backend/inventory/__init__.py
touch infraai/backend/api/__init__.py
touch infraai/backend/tests/__init__.py
```

- [ ] **Step 2: Crea `infraai/backend/requirements.txt`**

```
fastapi==0.115.5
uvicorn[standard]==0.32.1
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
alembic==1.14.0
pydantic-settings==2.6.1
httpx==0.28.0
python-multipart==0.0.17
aiofiles==24.1.0
```

- [ ] **Step 3: Crea `infraai/backend/requirements-dev.txt`**

```
pytest==8.3.3
pytest-asyncio==0.24.0
pytest-cov==6.0.0
respx==0.21.1
aiosqlite==0.20.0
```

- [ ] **Step 4: Crea `infraai/backend/pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
pythonpath = .
```

- [ ] **Step 5: Crea `infraai/.env.example`**

```env
# Database
DATABASE_URL=postgresql+asyncpg://infraai:infraai@db:5432/infraai

# Anthropic (Piano 2)
ANTHROPIC_API_KEY=sk-ant-...

# Zabbix
ZABBIX_URL=https://your-zabbix-server/zabbix
ZABBIX_TOKEN=your-zabbix-api-token

# Uptime Kuma
KUMA_URL=https://your-kuma-server
KUMA_API_KEY=your-kuma-api-key

# Telegram (Piano 3)
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_CHAT_ID=your-telegram-chat-id

# Security
AUTH_PASSWORD=change-me-strong-password
ALLOWED_IPS=1.2.3.4,5.6.7.8
```

- [ ] **Step 6: Crea `infraai/backend/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://infraai:infraai@db:5432/infraai"
    anthropic_api_key: str = ""
    zabbix_url: str = ""
    zabbix_token: str = ""
    kuma_url: str = ""
    kuma_api_key: str = ""
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    auth_password: str = "changeme"
    allowed_ips: str = ""


settings = Settings()
```

- [ ] **Step 7: Crea `infraai/backend/database.py`**

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from .config import settings


engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 8: Crea `infraai/backend/main.py`**

```python
from fastapi import FastAPI

app = FastAPI(title="InfraAI", version="1.0.0")


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 9: Crea `infraai/backend/Dockerfile`**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 10: Crea `infraai/docker-compose.yml`**

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: infraai
      POSTGRES_PASSWORD: infraai
      POSTGRES_DB: infraai
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U infraai"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build: ./backend
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./backend:/app

volumes:
  pgdata:
```

- [ ] **Step 11: Copia `.env.example` in `.env` e inserisci i valori reali**

```bash
cp infraai/.env.example infraai/.env
# Edita infraai/.env con i tuoi valori reali (Zabbix token, Kuma key, ecc.)
```

- [ ] **Step 12: Commit**

```bash
cd infraai
git init
git add .
git commit -m "feat: project foundation — docker-compose, config, fastapi skeleton"
```

---

### Task 2: Database Models + Migrations

**Files:**
- Create: `infraai/backend/models/server.py`
- Create: `infraai/backend/models/audit.py`
- Modify: `infraai/backend/models/__init__.py`
- Create: `infraai/backend/alembic/` (generato da alembic)

- [ ] **Step 1: Installa dipendenze in locale per sviluppo e test**

```bash
cd infraai/backend
pip install -r requirements.txt -r requirements-dev.txt
```

- [ ] **Step 2: Crea `infraai/backend/models/server.py`**

```python
import enum
from datetime import datetime
from sqlalchemy import String, Enum as SAEnum, DateTime, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base


class OSFamily(str, enum.Enum):
    ubuntu = "ubuntu"
    debian = "debian"
    centos = "centos"
    almalinux = "almalinux"
    windows = "windows"
    other = "other"


class AnsibleController(str, enum.Enum):
    stable = "stable"
    new = "new"
    auto = "auto"


class Provider(str, enum.Enum):
    hetzner = "hetzner"
    contabo = "contabo"
    vh = "vh"
    physical = "physical"
    other = "other"


class Server(Base):
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(primary_key=True)
    hostname: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    os_family: Mapped[OSFamily | None] = mapped_column(SAEnum(OSFamily), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    provider: Mapped[Provider] = mapped_column(SAEnum(Provider), default=Provider.other)
    cliente: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    ruolo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    ansible_controller: Mapped[AnsibleController] = mapped_column(
        SAEnum(AnsibleController), default=AnsibleController.auto
    )
    source: Mapped[str] = mapped_column(String(50))  # "zabbix" | "rdm" | "yaml"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
```

- [ ] **Step 3: Crea `infraai/backend/models/audit.py`**

```python
from datetime import datetime
from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base


class CommandHistory(Base):
    __tablename__ = "command_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_message: Mapped[str] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    targets: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list of hostnames
    status: Mapped[str] = mapped_column(String(50), default="pending")
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 4: Aggiorna `infraai/backend/models/__init__.py`**

```python
from .server import Server, OSFamily, AnsibleController, Provider
from .audit import CommandHistory

__all__ = ["Server", "OSFamily", "AnsibleController", "Provider", "CommandHistory"]
```

- [ ] **Step 5: Inizializza Alembic**

```bash
cd infraai/backend
alembic init alembic
```

Expected: crea `alembic/` directory e `alembic.ini`

- [ ] **Step 6: Aggiorna `infraai/backend/alembic/env.py`** — sostituisci il contenuto generato con:

```python
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from config import settings
from database import Base
import models  # noqa: F401 — registra tutti i modelli in Base.metadata

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 7: Genera la prima migration**

```bash
cd infraai/backend
alembic revision --autogenerate -m "initial schema"
```

Expected: crea `alembic/versions/xxxx_initial_schema.py` con le tabelle `servers` e `command_history`

- [ ] **Step 8: Avvia PostgreSQL e applica la migration**

```bash
cd infraai
docker compose up db -d
# Attendi ~5 secondi che PostgreSQL sia healthy
cd backend
DATABASE_URL=postgresql+asyncpg://infraai:infraai@localhost:5432/infraai alembic upgrade head
```

Expected: `Running upgrade -> xxxx, initial schema`

- [ ] **Step 9: Commit**

```bash
cd infraai
git add backend/models/ backend/alembic/ backend/alembic.ini
git commit -m "feat: database models — Server, CommandHistory + alembic migrations"
```

---

### Task 3: Zabbix Client

**Files:**
- Create: `infraai/backend/tests/conftest.py`
- Create: `infraai/backend/tests/test_zabbix_client.py`
- Create: `infraai/backend/inventory/zabbix_client.py`

- [ ] **Step 1: Crea `infraai/backend/tests/conftest.py`**

```python
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from database import Base
import models  # noqa: registra tutti i modelli con Base.metadata


TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()
```

- [ ] **Step 2: Crea `infraai/backend/tests/test_zabbix_client.py`**

```python
import pytest
import respx
import httpx
from inventory.zabbix_client import ZabbixClient


ZABBIX_URL = "https://zabbix.example.com"
ZABBIX_TOKEN = "test-token-123"


@pytest.mark.asyncio
async def test_get_all_hosts_returns_list():
    """get_all_hosts() ritorna una lista di dict con hostname e ip."""
    mock_response = {
        "jsonrpc": "2.0",
        "result": [
            {
                "hostid": "10001",
                "host": "win-srv-01",
                "name": "Windows Server 01",
                "interfaces": [{"ip": "192.168.1.10", "type": "1"}],
            }
        ],
        "id": 1,
    }
    with respx.mock:
        respx.post(f"{ZABBIX_URL}/api_jsonrpc.php").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        client = ZabbixClient(url=ZABBIX_URL, token=ZABBIX_TOKEN)
        hosts = await client.get_all_hosts()
        await client.close()

    assert isinstance(hosts, list)
    assert len(hosts) == 1
    assert hosts[0]["host"] == "win-srv-01"
    assert hosts[0]["ip"] == "192.168.1.10"


@pytest.mark.asyncio
async def test_get_all_hosts_raises_on_zabbix_error():
    """get_all_hosts() lancia ValueError quando Zabbix risponde con un errore."""
    mock_response = {
        "jsonrpc": "2.0",
        "error": {"code": -32602, "message": "Invalid params"},
        "id": 1,
    }
    with respx.mock:
        respx.post(f"{ZABBIX_URL}/api_jsonrpc.php").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        client = ZabbixClient(url=ZABBIX_URL, token=ZABBIX_TOKEN)
        with pytest.raises(ValueError, match="Zabbix API error"):
            await client.get_all_hosts()
        await client.close()
```

- [ ] **Step 3: Esegui i test — verifica che falliscono**

```bash
cd infraai/backend
pytest tests/test_zabbix_client.py -v
```

Expected: `FAILED ... ModuleNotFoundError: No module named 'inventory.zabbix_client'`

- [ ] **Step 4: Crea `infraai/backend/inventory/zabbix_client.py`**

```python
from typing import Any
import httpx


class ZabbixClient:
    def __init__(self, url: str, token: str):
        self._url = url.rstrip("/") + "/api_jsonrpc.php"
        self._token = token
        self._client = httpx.AsyncClient(timeout=30.0)

    async def _call(self, method: str, params: dict) -> Any:
        payload = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
            "auth": self._token,
            "id": 1,
        }
        response = await self._client.post(self._url, json=payload)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise ValueError(f"Zabbix API error: {data['error']['message']}")
        return data["result"]

    async def get_all_hosts(self) -> list[dict]:
        """Recupera tutti gli host attivi da Zabbix. In questo setup sono tutti Windows."""
        raw = await self._call(
            "host.get",
            {
                "output": ["hostid", "host", "name"],
                "selectInterfaces": ["ip", "type"],
                "filter": {"status": 0},
            },
        )
        result = []
        for h in raw:
            interfaces = h.get("interfaces", [])
            ip = next((i["ip"] for i in interfaces if i.get("type") == "1"), None)
            if ip is None and interfaces:
                ip = interfaces[0]["ip"]
            result.append({"hostid": h["hostid"], "host": h["host"], "name": h["name"], "ip": ip})
        return result

    async def close(self) -> None:
        await self._client.aclose()
```

- [ ] **Step 5: Esegui i test — verifica che passano**

```bash
cd infraai/backend
pytest tests/test_zabbix_client.py -v
```

Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
cd infraai
git add backend/inventory/zabbix_client.py backend/tests/
git commit -m "feat: Zabbix async JSON-RPC client"
```

---

### Task 4: Uptime Kuma Client

**Files:**
- Create: `infraai/backend/tests/test_kuma_client.py`
- Create: `infraai/backend/inventory/kuma_client.py`

- [ ] **Step 1: Crea `infraai/backend/tests/test_kuma_client.py`**

```python
import pytest
import respx
import httpx
from inventory.kuma_client import KumaClient


KUMA_URL = "https://kuma.example.com"
KUMA_KEY = "test-api-key"


@pytest.mark.asyncio
async def test_get_monitors_returns_list():
    """get_monitors() ritorna una lista di monitor dict."""
    mock_response = {
        "monitors": [
            {"id": 1, "name": "Site Rossi", "url": "https://rossi.example.com", "active": True, "status": 1}
        ]
    }
    with respx.mock:
        respx.get(f"{KUMA_URL}/api/monitors").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        client = KumaClient(url=KUMA_URL, api_key=KUMA_KEY)
        monitors = await client.get_monitors()
        await client.close()

    assert isinstance(monitors, list)
    assert len(monitors) == 1
    assert monitors[0]["name"] == "Site Rossi"


@pytest.mark.asyncio
async def test_get_monitors_raises_on_http_error():
    """get_monitors() lancia HTTPStatusError su risposta non-200."""
    with respx.mock:
        respx.get(f"{KUMA_URL}/api/monitors").mock(return_value=httpx.Response(401))
        client = KumaClient(url=KUMA_URL, api_key=KUMA_KEY)
        with pytest.raises(httpx.HTTPStatusError):
            await client.get_monitors()
        await client.close()
```

- [ ] **Step 2: Esegui i test — verifica che falliscono**

```bash
cd infraai/backend
pytest tests/test_kuma_client.py -v
```

Expected: `FAILED ... ModuleNotFoundError: No module named 'inventory.kuma_client'`

- [ ] **Step 3: Crea `infraai/backend/inventory/kuma_client.py`**

```python
import httpx


class KumaClient:
    def __init__(self, url: str, api_key: str):
        self._url = url.rstrip("/")
        self._client = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )

    async def get_monitors(self) -> list[dict]:
        """Recupera tutti i monitor da Uptime Kuma."""
        response = await self._client.get(f"{self._url}/api/monitors")
        response.raise_for_status()
        return response.json().get("monitors", [])

    async def close(self) -> None:
        await self._client.aclose()
```

- [ ] **Step 4: Esegui i test — verifica che passano**

```bash
cd infraai/backend
pytest tests/test_kuma_client.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
cd infraai
git add backend/inventory/kuma_client.py backend/tests/test_kuma_client.py
git commit -m "feat: Uptime Kuma async REST client"
```

---

### Task 5: RDM CSV Importer

**Files:**
- Create: `infraai/backend/tests/test_rdm_importer.py`
- Create: `infraai/backend/inventory/rdm_importer.py`

Remote Desktop Manager esporta CSV con colonne: `Name` (hostname), `Host` (IP), `Description`, `Group` (cliente).

- [ ] **Step 1: Crea `infraai/backend/tests/test_rdm_importer.py`**

```python
import io
import pytest
from sqlalchemy import select
from inventory.rdm_importer import RDMImporter
from models.server import Server, OSFamily


SAMPLE_CSV = """Name,Host,Description,Group
srv-web-01,192.168.1.100,Web server principale,Rossi Srl
srv-db-01,192.168.1.101,Database PostgreSQL,Rossi Srl
srv-proxy-01,10.0.0.5,Proxy nginx,Bianchi SpA
"""


@pytest.mark.asyncio
async def test_import_creates_servers(db_session):
    """import_csv() crea record Server dal contenuto CSV."""
    importer = RDMImporter(db_session)
    count = await importer.import_csv(io.StringIO(SAMPLE_CSV))

    assert count == 3
    result = await db_session.execute(select(Server))
    servers = result.scalars().all()
    assert len(servers) == 3


@pytest.mark.asyncio
async def test_import_maps_fields_correctly(db_session):
    """import_csv() mappa correttamente colonne CSV → campi Server."""
    importer = RDMImporter(db_session)
    await importer.import_csv(io.StringIO(SAMPLE_CSV))

    result = await db_session.execute(select(Server).where(Server.hostname == "srv-web-01"))
    server = result.scalar_one()

    assert server.ip == "192.168.1.100"
    assert server.cliente == "Rossi Srl"
    assert server.source == "rdm"
    assert server.os_family == OSFamily.ubuntu  # default Linux da RDM = ubuntu


@pytest.mark.asyncio
async def test_import_upserts_on_duplicate_hostname(db_session):
    """import_csv() aggiorna il server esistente su hostname duplicato."""
    importer = RDMImporter(db_session)
    await importer.import_csv(io.StringIO(SAMPLE_CSV))

    updated_csv = "Name,Host,Description,Group\nsrv-web-01,192.168.1.200,Updated,Rossi Srl\n"
    await importer.import_csv(io.StringIO(updated_csv))

    result = await db_session.execute(select(Server).where(Server.hostname == "srv-web-01"))
    server = result.scalar_one()
    assert server.ip == "192.168.1.200"

    all_servers = await db_session.execute(select(Server))
    assert len(all_servers.scalars().all()) == 3  # nessun duplicato
```

- [ ] **Step 2: Esegui i test — verifica che falliscono**

```bash
cd infraai/backend
pytest tests/test_rdm_importer.py -v
```

Expected: `FAILED ... ModuleNotFoundError`

- [ ] **Step 3: Crea `infraai/backend/inventory/rdm_importer.py`**

```python
import csv
from datetime import datetime
from io import StringIO
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models.server import Server, OSFamily, AnsibleController


class RDMImporter:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def import_csv(self, csv_file: StringIO) -> int:
        """Parsa il CSV di RDM e fa upsert dei record Server. Ritorna il numero di righe processate."""
        reader = csv.DictReader(csv_file)
        count = 0
        for row in reader:
            hostname = (row.get("Name") or "").strip()
            if not hostname:
                continue
            ip = (row.get("Host") or "").strip() or None
            cliente = (row.get("Group") or "").strip() or None
            note = (row.get("Description") or "").strip() or None

            result = await self._session.execute(
                select(Server).where(Server.hostname == hostname)
            )
            server = result.scalar_one_or_none()

            if server:
                server.ip = ip
                server.cliente = cliente
                server.note = note
                server.updated_at = datetime.utcnow()
            else:
                server = Server(
                    hostname=hostname,
                    ip=ip,
                    cliente=cliente,
                    note=note,
                    os_family=OSFamily.ubuntu,  # default: Linux da RDM è ubuntu
                    ansible_controller=AnsibleController.auto,
                    source="rdm",
                )
                self._session.add(server)
            count += 1

        await self._session.commit()
        return count
```

- [ ] **Step 4: Esegui i test — verifica che passano**

```bash
cd infraai/backend
pytest tests/test_rdm_importer.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
cd infraai
git add backend/inventory/rdm_importer.py backend/tests/test_rdm_importer.py
git commit -m "feat: RDM CSV importer with upsert logic"
```

---

### Task 6: Inventory Sync Orchestrator

**Files:**
- Create: `infraai/backend/tests/test_sync.py`
- Create: `infraai/backend/inventory/sync.py`

- [ ] **Step 1: Crea `infraai/backend/tests/test_sync.py`**

```python
from unittest.mock import AsyncMock, patch
import pytest
from sqlalchemy import select
from inventory.sync import InventorySync
from models.server import Server, OSFamily


FAKE_ZABBIX_HOSTS = [
    {"hostid": "1001", "host": "win-srv-01", "name": "Windows Server 01", "ip": "10.0.0.10"},
    {"hostid": "1002", "host": "win-srv-02", "name": "Windows Server 02", "ip": "10.0.0.11"},
]


@pytest.mark.asyncio
async def test_sync_zabbix_creates_windows_servers(db_session):
    """sync_zabbix() crea Server con os_family=windows per ogni host Zabbix."""
    sync = InventorySync(db_session)
    with patch.object(sync._zabbix, "get_all_hosts", new=AsyncMock(return_value=FAKE_ZABBIX_HOSTS)):
        count = await sync.sync_zabbix()

    assert count == 2
    result = await db_session.execute(select(Server).where(Server.source == "zabbix"))
    servers = result.scalars().all()
    assert len(servers) == 2
    assert all(s.os_family == OSFamily.windows for s in servers)


@pytest.mark.asyncio
async def test_sync_zabbix_upserts_ip_on_resync(db_session):
    """sync_zabbix() aggiorna l'IP se il server esiste già."""
    sync = InventorySync(db_session)
    hosts_v1 = [{"hostid": "1001", "host": "win-srv-01", "name": "Win 01", "ip": "10.0.0.10"}]
    hosts_v2 = [{"hostid": "1001", "host": "win-srv-01", "name": "Win 01", "ip": "10.0.0.99"}]

    with patch.object(sync._zabbix, "get_all_hosts", new=AsyncMock(return_value=hosts_v1)):
        await sync.sync_zabbix()
    with patch.object(sync._zabbix, "get_all_hosts", new=AsyncMock(return_value=hosts_v2)):
        await sync.sync_zabbix()

    result = await db_session.execute(select(Server).where(Server.hostname == "win-srv-01"))
    server = result.scalar_one()
    assert server.ip == "10.0.0.99"

    all_result = await db_session.execute(select(Server))
    assert len(all_result.scalars().all()) == 1  # nessun duplicato
```

- [ ] **Step 2: Esegui i test — verifica che falliscono**

```bash
cd infraai/backend
pytest tests/test_sync.py -v
```

Expected: `FAILED ... ModuleNotFoundError`

- [ ] **Step 3: Crea `infraai/backend/inventory/sync.py`**

```python
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .zabbix_client import ZabbixClient
from .kuma_client import KumaClient
from models.server import Server, OSFamily, AnsibleController
from config import settings


class InventorySync:
    def __init__(self, session: AsyncSession):
        self._session = session
        self._zabbix = ZabbixClient(url=settings.zabbix_url, token=settings.zabbix_token)
        self._kuma = KumaClient(url=settings.kuma_url, api_key=settings.kuma_api_key)

    async def sync_zabbix(self) -> int:
        """Sincronizza i server Windows da Zabbix. Ritorna il numero di record upsertati."""
        hosts = await self._zabbix.get_all_hosts()
        count = 0
        now = datetime.utcnow()
        for h in hosts:
            result = await self._session.execute(
                select(Server).where(Server.hostname == h["host"])
            )
            server = result.scalar_one_or_none()

            if server:
                server.ip = h.get("ip")
                server.last_seen = now
                server.updated_at = now
            else:
                server = Server(
                    hostname=h["host"],
                    ip=h.get("ip"),
                    os_family=OSFamily.windows,
                    ansible_controller=AnsibleController.auto,
                    source="zabbix",
                    last_seen=now,
                )
                self._session.add(server)
            count += 1

        await self._session.commit()
        return count

    async def close(self) -> None:
        await self._zabbix.close()
        await self._kuma.close()
```

- [ ] **Step 4: Esegui i test — verifica che passano**

```bash
cd infraai/backend
pytest tests/test_sync.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Esegui tutta la suite**

```bash
cd infraai/backend
pytest tests/ -v --tb=short
```

Expected: tutti `passed` (Zabbix + Kuma + RDM + Sync)

- [ ] **Step 6: Commit**

```bash
cd infraai
git add backend/inventory/sync.py backend/tests/test_sync.py
git commit -m "feat: inventory sync orchestrator — Zabbix + Kuma upsert"
```

---

### Task 7: Inventory API Endpoints

**Files:**
- Create: `infraai/backend/api/inventory.py`
- Modify: `infraai/backend/main.py`

- [ ] **Step 1: Crea `infraai/backend/api/inventory.py`**

```python
from io import StringIO
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models.server import Server
from inventory.rdm_importer import RDMImporter
from inventory.sync import InventorySync


router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.get("/servers")
async def list_servers(
    cliente: str | None = None,
    source: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Lista tutti i server, opzionalmente filtrati per cliente o source."""
    query = select(Server).where(Server.is_active == True)
    if cliente:
        query = query.where(Server.cliente == cliente)
    if source:
        query = query.where(Server.source == source)
    result = await db.execute(query)
    return [
        {
            "id": s.id,
            "hostname": s.hostname,
            "ip": s.ip,
            "os_family": s.os_family,
            "os_version": s.os_version,
            "cliente": s.cliente,
            "ruolo": s.ruolo,
            "source": s.source,
            "ansible_controller": s.ansible_controller,
            "last_seen": s.last_seen,
        }
        for s in result.scalars().all()
    ]


@router.post("/import-rdm-csv")
async def import_rdm_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Importa server Linux dal CSV esportato da Remote Desktop Manager."""
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Il file deve essere .csv")
    content = await file.read()
    csv_text = content.decode("utf-8-sig")  # gestisce BOM da export Windows
    importer = RDMImporter(db)
    count = await importer.import_csv(StringIO(csv_text))
    return {"imported": count}


@router.post("/sync-zabbix")
async def sync_zabbix(db: AsyncSession = Depends(get_db)):
    """Avvia manualmente la sync Zabbix (server Windows)."""
    sync = InventorySync(db)
    try:
        count = await sync.sync_zabbix()
    finally:
        await sync.close()
    return {"synced": count}
```

- [ ] **Step 2: Aggiorna `infraai/backend/main.py`**

```python
from fastapi import FastAPI
from api.inventory import router as inventory_router

app = FastAPI(title="InfraAI", version="1.0.0")

app.include_router(inventory_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 3: Avvia il backend in locale e verifica**

```bash
cd infraai
docker compose up db -d
cd backend
DATABASE_URL=postgresql+asyncpg://infraai:infraai@localhost:5432/infraai uvicorn main:app --reload --port 8000
```

- [ ] **Step 4: Testa gli endpoint (in un secondo terminale)**

```bash
# Health check
curl http://localhost:8000/health
# Expected: {"status":"ok"}

# Lista server (vuota)
curl http://localhost:8000/api/inventory/servers
# Expected: []

# Import CSV di test
printf "Name,Host,Description,Group\nsrv-test-01,10.0.0.50,Test server,Cliente Test\n" > /tmp/test.csv
curl -F "file=@/tmp/test.csv" http://localhost:8000/api/inventory/import-rdm-csv
# Expected: {"imported":1}

# Verifica server importato
curl http://localhost:8000/api/inventory/servers
# Expected: [{"hostname":"srv-test-01","ip":"10.0.0.50","cliente":"Cliente Test",...}]

# Filtro per cliente
curl "http://localhost:8000/api/inventory/servers?cliente=Cliente+Test"
# Expected: lista con solo srv-test-01
```

- [ ] **Step 5: Commit**

```bash
cd infraai
git add backend/api/inventory.py backend/main.py
git commit -m "feat: inventory REST API — list, import RDM CSV, sync Zabbix"
```

---

### Task 8: Nginx + IP Whitelist + SSL

**Files:**
- Create: `infraai/nginx/whitelist.conf`
- Create: `infraai/nginx/nginx.conf`

Questi passi si eseguono **sulla VPS AI Brain** (non in locale).

- [ ] **Step 1: Crea `infraai/nginx/whitelist.conf`**

Inserisci i tuoi IP reali:
```nginx
allow 1.2.3.4;      # Sostituisci con il tuo IP statico principale
# allow 5.6.7.8;   # Secondo IP autorizzato (scommenta per abilitare)
deny all;
```

- [ ] **Step 2: Crea `infraai/nginx/nginx.conf`**

```nginx
events {}

http {
    server {
        listen 80;
        server_name _;
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl;
        server_name _;

        ssl_certificate     /etc/letsencrypt/live/infraai/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/infraai/privkey.pem;

        include /etc/nginx/whitelist.conf;

        location /api/ {
            proxy_pass http://127.0.0.1:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        location /health {
            proxy_pass http://127.0.0.1:8000/health;
        }

        location / {
            proxy_pass http://127.0.0.1:3000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
}
```

- [ ] **Step 3: Installa nginx e certbot sulla VPS**

```bash
sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx
sudo systemctl enable nginx
```

- [ ] **Step 4: Ottieni il certificato SSL**

```bash
sudo certbot certonly --standalone -d tuo-dominio.example.com
# Segui le istruzioni. Il certificato viene salvato in /etc/letsencrypt/live/tuo-dominio.example.com/
```

Poi aggiorna i path in `nginx.conf` sostituendo `infraai` con il nome del dominio usato.

- [ ] **Step 5: Copia configurazione e riavvia nginx**

```bash
sudo cp infraai/nginx/nginx.conf /etc/nginx/nginx.conf
sudo cp infraai/nginx/whitelist.conf /etc/nginx/whitelist.conf
sudo nginx -t
```

Expected: `syntax is ok` e `test is successful`

```bash
sudo systemctl reload nginx
```

- [ ] **Step 6: Avvia lo stack Docker completo**

```bash
cd infraai
docker compose up -d
```

Expected: container `db` e `backend` in stato `Up`

- [ ] **Step 7: Verifica da browser o curl dal tuo IP**

```bash
curl https://tuo-dominio.example.com/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 8: Commit**

```bash
cd infraai
git add nginx/
git commit -m "feat: nginx reverse proxy with IP whitelist and SSL termination"
```

---

## Self-Review — Copertura Spec

| Requisito spec (Piano 1) | Task |
|---|---|
| VPS dedicata + Docker Compose | Task 1 |
| PostgreSQL schema — Server + CommandHistory | Task 2 |
| Zabbix API client (Windows) | Task 3 |
| Uptime Kuma client | Task 4 |
| RDM CSV importer con upsert | Task 5 |
| Sync orchestrator | Task 6 |
| REST API: list, import CSV, sync | Task 7 |
| Nginx IP whitelist + SSL | Task 8 |

**Rinviato ai piani successivi:**
- Ansible Router + routing OS (Piano 2)
- Claude AI + intent parsing + chat API (Piano 2)
- Next.js frontend (Piano 3)
- Telegram bot + alert engine (Piano 3)
- Regole di autonomia (Piano 2)
- Workflow upgrade OS 22.04→24.04 (Piano 2)
