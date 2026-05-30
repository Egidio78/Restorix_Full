# InfraAI Piano 3a: Telegram Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Telegram bot that sends proactive Zabbix/Kuma infrastructure alerts and executes Italian natural language commands via the InfraAI backend.

**Architecture:** The `telegram_bot` is a separate Python container sharing the PostgreSQL database with the backend. It polls Zabbix and Uptime Kuma every 5 minutes for active problems, sends severity-tiered alerts with deduplication, handles `/silence hostname duration` commands (stored in DB), forwards natural language messages to the backend chat SSE API, and sends a daily health report at 08:00.

**Tech Stack:** python-telegram-bot 21.6.1 (async + built-in APScheduler job_queue), httpx 0.28, SQLAlchemy 2.0 async, asyncpg, pydantic-settings 2.6

---

## File Structure

```
telegram_bot/
  config.py            — Settings (reads same .env via pydantic-settings)
  db.py                — async SQLAlchemy engine + session factory
  silence.py           — Silence ORM model + SilenceStore (add/check/expire)
  monitors.py          — ZabbixChecker + KumaChecker → list[Alert]
  backend_client.py    — stream chat API SSE, accumulate text
  bot.py               — Application setup, /silence handler, message handler, scheduler jobs
  main.py              — entry point (asyncio.run)
  requirements.txt
  requirements-dev.txt
  pytest.ini
  tests/
    conftest.py        — in-memory SQLite db_session fixture
    test_silence.py    — SilenceStore add/check/expire
    test_monitors.py   — alert checking with mocked httpx
    test_backend_client.py — SSE parsing with mocked httpx
    test_bot.py        — command/message handlers with mocked Telegram objects
  Dockerfile

backend/models/silence.py          — Silence SQLAlchemy model (used by Alembic)
backend/alembic/versions/b2c3d4e5f6a1_add_silences_table.py  — migration
```

---

### Task 1: Silence Model + Alembic Migration

Adds the `silences` table to the shared PostgreSQL database. The telegram bot reads/writes this table to track silenced servers. The migration is hand-written (no Docker for autogenerate).

**Files:**
- Create: `backend/models/silence.py`
- Modify: `backend/models/__init__.py` (if exists, else skip)
- Create: `backend/alembic/versions/b2c3d4e5f6a1_add_silences_table.py`
- Modify: `backend/alembic/env.py` (import new model so Alembic sees it)

- [ ] **Step 1: Create `backend/models/silence.py`**

```python
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Silence(Base):
    __tablename__ = "silences"

    id: Mapped[int] = mapped_column(primary_key=True)
    hostname: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    silenced_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
```

- [ ] **Step 2: Import Silence in `backend/alembic/env.py` so Alembic is aware**

Read `backend/alembic/env.py`. Find the line that imports models (it should have `from models.server import ...` or similar `target_metadata = Base.metadata`). Add:

```python
from models.silence import Silence  # noqa: F401 — registers table with Base.metadata
```

Place it alongside the other model imports, before `target_metadata = Base.metadata`.

- [ ] **Step 3: Write the Alembic migration**

Create `backend/alembic/versions/b2c3d4e5f6a1_add_silences_table.py`:

```python
"""add silences table

Revision ID: b2c3d4e5f6a1
Revises: 69ff7343c5ab
Create Date: 2026-05-10 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a1"
down_revision = "69ff7343c5ab"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "silences",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hostname", sa.String(255), nullable=False),
        sa.Column("silenced_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_silences_hostname", "silences", ["hostname"])


def downgrade() -> None:
    op.drop_index("ix_silences_hostname", table_name="silences")
    op.drop_table("silences")
```

- [ ] **Step 4: Verify migration chain is correct**

The `down_revision` must match the revision ID in the existing `backend/alembic/versions/69ff7343_initial_schema.py`. Read that file and confirm the `revision` value is `"69ff7343c5ab"` (or whatever the exact hex is). If it differs, update `down_revision` accordingly.

- [ ] **Step 5: Verify the model imports correctly**

```bash
cd D:\Claude_Code\infraai\backend
python -c "from models.silence import Silence; print(Silence.__tablename__)"
```

Expected output: `silences`

- [ ] **Step 6: Commit**

```bash
git -C D:\Claude_Code\infraai add backend/models/silence.py backend/alembic/versions/b2c3d4e5f6a1_add_silences_table.py backend/alembic/env.py
git -C D:\Claude_Code\infraai commit -m "feat: add silences table model and migration"
```

---

### Task 2: Telegram Bot Project Scaffold

Sets up the telegram_bot directory with config, database connection, requirements, pytest, and Dockerfile. No logic yet — just the skeleton.

**Files:**
- Create: `telegram_bot/config.py`
- Create: `telegram_bot/db.py`
- Create: `telegram_bot/requirements.txt`
- Create: `telegram_bot/requirements-dev.txt`
- Create: `telegram_bot/pytest.ini`
- Create: `telegram_bot/tests/__init__.py`
- Create: `telegram_bot/tests/conftest.py`
- Create: `telegram_bot/Dockerfile`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Create `telegram_bot/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    database_url: str = "postgresql+asyncpg://infraai:infraai@db:5432/infraai"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    zabbix_url: str = ""
    zabbix_token: str = ""
    kuma_url: str = ""
    kuma_api_key: str = ""

    # Backend chat API (for natural language forwarding)
    backend_url: str = "http://backend:8000"
    auth_password: str = "changeme"


settings = Settings()
```

- [ ] **Step 2: Create `telegram_bot/db.py`**

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import settings

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 3: Create `telegram_bot/requirements.txt`**

```
python-telegram-bot[job-queue]==21.6.1
httpx==0.28.0
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
pydantic-settings==2.6.1
```

- [ ] **Step 4: Create `telegram_bot/requirements-dev.txt`**

```
pytest==8.3.3
pytest-asyncio==0.24.0
aiosqlite==0.20.0
respx==0.23.1
```

- [ ] **Step 5: Create `telegram_bot/pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
pythonpath = .
```

- [ ] **Step 6: Create `telegram_bot/tests/__init__.py`** (empty)

- [ ] **Step 7: Create `telegram_bot/tests/conftest.py`**

```python
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from db import Base


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
```

- [ ] **Step 8: Create `telegram_bot/Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

- [ ] **Step 9: Add telegram service to `docker-compose.yml`**

Read `docker-compose.yml`. Add this service alongside `infra-ai-backend`:

```yaml
  infra-ai-telegram:
    build: ./telegram_bot
    restart: unless-stopped
    env_file: .env
    depends_on:
      infra-ai-db:
        condition: service_healthy
      infra-ai-backend:
        condition: service_started
    volumes:
      - ./telegram_bot:/app
    working_dir: /app
```

- [ ] **Step 10: Verify scaffold imports work**

```bash
cd D:\Claude_Code\infraai\telegram_bot
pip install -r requirements.txt -r requirements-dev.txt --quiet
python -c "from config import settings; print('config ok')"
python -c "from db import Base; print('db ok')"
```

Expected: two lines of "ok".

- [ ] **Step 11: Commit**

```bash
git -C D:\Claude_Code\infraai add telegram_bot/ docker-compose.yml
git -C D:\Claude_Code\infraai commit -m "feat: telegram bot project scaffold with config, db, Dockerfile"
```

---

### Task 3: SilenceStore

Implements add/check/expire silence operations on the `silences` table. The `conftest.py` fixture provides an in-memory SQLite session with the schema auto-created from the `Silence` model defined in `telegram_bot/silence.py` (mirrors the backend model but uses `telegram_bot/db.py`'s `Base`).

**Files:**
- Create: `telegram_bot/silence.py`
- Create: `telegram_bot/tests/test_silence.py`

- [ ] **Step 1: Write failing tests in `telegram_bot/tests/test_silence.py`**

```python
from datetime import datetime, timedelta, timezone

import pytest

from silence import Silence, SilenceStore


@pytest.mark.asyncio
async def test_add_silence_marks_host_as_silenced(db_session):
    store = SilenceStore(db_session)
    until = datetime.now(timezone.utc) + timedelta(hours=2)
    await store.add(hostname="srv-01", silenced_until=until)

    assert await store.is_silenced("srv-01") is True


@pytest.mark.asyncio
async def test_unsilenced_host_returns_false(db_session):
    store = SilenceStore(db_session)
    assert await store.is_silenced("srv-99") is False


@pytest.mark.asyncio
async def test_expired_silence_returns_false(db_session):
    store = SilenceStore(db_session)
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    await store.add(hostname="srv-02", silenced_until=past)

    assert await store.is_silenced("srv-02") is False


@pytest.mark.asyncio
async def test_clear_expired_removes_past_silences(db_session):
    store = SilenceStore(db_session)
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    await store.add(hostname="old-srv", silenced_until=past)
    await store.add(hostname="new-srv", silenced_until=future)

    deleted = await store.clear_expired()

    assert deleted == 1
    assert await store.is_silenced("new-srv") is True


@pytest.mark.asyncio
async def test_get_silence_returns_until_datetime(db_session):
    store = SilenceStore(db_session)
    until = datetime.now(timezone.utc) + timedelta(hours=3)
    await store.add(hostname="srv-03", silenced_until=until)

    result = await store.get_silence("srv-03")
    assert result is not None
    assert abs((result - until).total_seconds()) < 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd D:\Claude_Code\infraai\telegram_bot
python -m pytest tests/test_silence.py -v
```

Expected: `ImportError: cannot import name 'Silence' from 'silence'`

- [ ] **Step 3: Create `telegram_bot/silence.py`**

```python
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Silence(Base):
    __tablename__ = "silences"

    id: Mapped[int] = mapped_column(primary_key=True)
    hostname: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    silenced_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )


class SilenceStore:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, hostname: str, silenced_until: datetime) -> None:
        silence = Silence(hostname=hostname, silenced_until=silenced_until)
        self._session.add(silence)
        await self._session.commit()

    async def is_silenced(self, hostname: str) -> bool:
        now = datetime.now(timezone.utc)
        stmt = select(func.count()).select_from(Silence).where(
            Silence.hostname == hostname,
            Silence.silenced_until > now,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one() > 0

    async def get_silence(self, hostname: str) -> datetime | None:
        now = datetime.now(timezone.utc)
        stmt = select(Silence.silenced_until).where(
            Silence.hostname == hostname,
            Silence.silenced_until > now,
        ).order_by(Silence.silenced_until.desc()).limit(1)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def clear_expired(self) -> int:
        now = datetime.now(timezone.utc)
        stmt = delete(Silence).where(Silence.silenced_until <= now)
        result = await self._session.execute(stmt)
        await self._session.commit()
        return result.rowcount
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd D:\Claude_Code\infraai\telegram_bot
python -m pytest tests/test_silence.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git -C D:\Claude_Code\infraai add telegram_bot/silence.py telegram_bot/tests/test_silence.py
git -C D:\Claude_Code\infraai commit -m "feat: silence store adds/checks/expires server silences"
```

---

### Task 4: Monitor Checker (Zabbix + Kuma)

Polls Zabbix for active trigger problems and Kuma for down monitors. Returns `Alert` dataclasses. Tests mock httpx with respx — no real API calls.

**Files:**
- Create: `telegram_bot/monitors.py`
- Create: `telegram_bot/tests/test_monitors.py`

- [ ] **Step 1: Write failing tests in `telegram_bot/tests/test_monitors.py`**

```python
import pytest
import respx
import httpx
from monitors import ZabbixChecker, KumaChecker, Alert, Severity


ZABBIX_URL = "http://zabbix.example.com"
KUMA_URL = "http://kuma.example.com"


@pytest.mark.asyncio
@respx.mock
async def test_zabbix_checker_returns_critical_alerts():
    respx.post(f"{ZABBIX_URL}/api_jsonrpc.php").mock(
        return_value=httpx.Response(200, json={
            "jsonrpc": "2.0",
            "id": 1,
            "result": [
                {
                    "triggerid": "101",
                    "description": "Disk space critical on srv-01",
                    "priority": "5",
                    "hosts": [{"host": "srv-01"}],
                }
            ],
        })
    )

    checker = ZabbixChecker(url=ZABBIX_URL, token="test-token")
    async with httpx.AsyncClient() as client:
        alerts = await checker.get_alerts(client)

    assert len(alerts) == 1
    assert alerts[0].hostname == "srv-01"
    assert alerts[0].severity == Severity.CRITICAL
    assert "Disk space" in alerts[0].description


@pytest.mark.asyncio
@respx.mock
async def test_zabbix_checker_returns_warning_alerts():
    respx.post(f"{ZABBIX_URL}/api_jsonrpc.php").mock(
        return_value=httpx.Response(200, json={
            "jsonrpc": "2.0",
            "id": 1,
            "result": [
                {
                    "triggerid": "202",
                    "description": "High CPU on srv-02",
                    "priority": "3",
                    "hosts": [{"host": "srv-02"}],
                }
            ],
        })
    )

    checker = ZabbixChecker(url=ZABBIX_URL, token="test-token")
    async with httpx.AsyncClient() as client:
        alerts = await checker.get_alerts(client)

    assert alerts[0].severity == Severity.WARNING


@pytest.mark.asyncio
@respx.mock
async def test_zabbix_checker_returns_empty_on_no_problems():
    respx.post(f"{ZABBIX_URL}/api_jsonrpc.php").mock(
        return_value=httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": []})
    )

    checker = ZabbixChecker(url=ZABBIX_URL, token="test-token")
    async with httpx.AsyncClient() as client:
        alerts = await checker.get_alerts(client)

    assert alerts == []


@pytest.mark.asyncio
@respx.mock
async def test_kuma_checker_returns_down_monitors():
    respx.get(f"{KUMA_URL}/api/monitors").mock(
        return_value=httpx.Response(200, json={
            "monitors": [
                {"id": 1, "name": "website-01", "active": True, "url": "https://site.example.com"},
                {"id": 2, "name": "api-gw", "active": False, "url": "https://api.example.com"},
            ]
        })
    )

    checker = KumaChecker(url=KUMA_URL, api_key="test-key")
    async with httpx.AsyncClient() as client:
        alerts = await checker.get_alerts(client)

    assert len(alerts) == 1
    assert alerts[0].hostname == "api-gw"
    assert alerts[0].severity == Severity.WARNING


@pytest.mark.asyncio
@respx.mock
async def test_kuma_checker_returns_empty_when_all_up():
    respx.get(f"{KUMA_URL}/api/monitors").mock(
        return_value=httpx.Response(200, json={
            "monitors": [
                {"id": 1, "name": "website-01", "active": True},
            ]
        })
    )

    checker = KumaChecker(url=KUMA_URL, api_key="test-key")
    async with httpx.AsyncClient() as client:
        alerts = await checker.get_alerts(client)

    assert alerts == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd D:\Claude_Code\infraai\telegram_bot
python -m pytest tests/test_monitors.py -v
```

Expected: `ImportError: cannot import name 'ZabbixChecker' from 'monitors'`

- [ ] **Step 3: Create `telegram_bot/monitors.py`**

```python
from dataclasses import dataclass
from enum import Enum

import httpx


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass(frozen=True)
class Alert:
    alert_id: str        # unique ID for deduplication
    hostname: str
    description: str
    severity: Severity


class ZabbixChecker:
    """Polls Zabbix for active trigger problems.

    Priority mapping:
      5 (Disaster) / 4 (High) → CRITICAL
      3 (Average) / 2 (Warning) / 1 (Information) → WARNING
    """

    def __init__(self, url: str, token: str) -> None:
        self._url = url.rstrip("/")
        self._token = token

    async def get_alerts(self, client: httpx.AsyncClient) -> list[Alert]:
        payload = {
            "jsonrpc": "2.0",
            "method": "trigger.get",
            "params": {
                "only_true": 1,
                "skipDependent": 1,
                "monitored": 1,
                "active": 1,
                "output": ["triggerid", "description", "priority"],
                "selectHosts": ["host"],
                "sortfield": "priority",
                "sortorder": "DESC",
            },
            "auth": self._token,
            "id": 1,
        }
        response = await client.post(f"{self._url}/api_jsonrpc.php", json=payload)
        response.raise_for_status()
        data = response.json()
        triggers = data.get("result") or []

        alerts = []
        for trigger in triggers:
            priority = int(trigger.get("priority", 0))
            if priority < 2:
                continue
            severity = Severity.CRITICAL if priority >= 4 else Severity.WARNING
            hostname = trigger["hosts"][0]["host"] if trigger.get("hosts") else "unknown"
            alerts.append(Alert(
                alert_id=f"zabbix-{trigger['triggerid']}",
                hostname=hostname,
                description=trigger.get("description", ""),
                severity=severity,
            ))
        return alerts


class KumaChecker:
    """Polls Uptime Kuma for monitors with active=False (down)."""

    def __init__(self, url: str, api_key: str) -> None:
        self._url = url.rstrip("/")
        self._api_key = api_key

    async def get_alerts(self, client: httpx.AsyncClient) -> list[Alert]:
        headers = {"Authorization": f"Bearer {self._api_key}"}
        response = await client.get(f"{self._url}/api/monitors", headers=headers)
        response.raise_for_status()
        monitors = response.json().get("monitors") or []

        alerts = []
        for monitor in monitors:
            if not monitor.get("active", True):
                alerts.append(Alert(
                    alert_id=f"kuma-{monitor['id']}",
                    hostname=monitor.get("name", "unknown"),
                    description=f"Monitor down: {monitor.get('url', '')}".strip(": "),
                    severity=Severity.WARNING,
                ))
        return alerts
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd D:\Claude_Code\infraai\telegram_bot
python -m pytest tests/test_monitors.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git -C D:\Claude_Code\infraai add telegram_bot/monitors.py telegram_bot/tests/test_monitors.py
git -C D:\Claude_Code\infraai commit -m "feat: zabbix and kuma alert checkers poll for active problems"
```

---

### Task 5: Backend Client (SSE Chat Forwarding)

Reads the SSE stream from the backend's `POST /api/chat/message` endpoint and returns the accumulated text. Tests mock httpx with respx.

**Files:**
- Create: `telegram_bot/backend_client.py`
- Create: `telegram_bot/tests/test_backend_client.py`

- [ ] **Step 1: Write failing tests in `telegram_bot/tests/test_backend_client.py`**

```python
import pytest
import respx
import httpx
from backend_client import send_chat_message


BACKEND_URL = "http://backend:8000"


@pytest.mark.asyncio
@respx.mock
async def test_send_chat_message_returns_accumulated_text():
    sse_body = (
        "data: Prima risposta\n\n"
        "data: Seconda risposta\n\n"
    )
    respx.post(f"{BACKEND_URL}/api/chat/message").mock(
        return_value=httpx.Response(
            200,
            content=sse_body.encode(),
            headers={"content-type": "text/event-stream"},
        )
    )

    result = await send_chat_message(
        message="aggiorna srv-01",
        backend_url=BACKEND_URL,
        password="changeme",
    )

    assert "Prima risposta" in result
    assert "Seconda risposta" in result


@pytest.mark.asyncio
@respx.mock
async def test_send_chat_message_handles_backend_error():
    respx.post(f"{BACKEND_URL}/api/chat/message").mock(
        return_value=httpx.Response(500)
    )

    result = await send_chat_message(
        message="test",
        backend_url=BACKEND_URL,
        password="changeme",
    )

    assert "errore" in result.lower() or "error" in result.lower()


@pytest.mark.asyncio
@respx.mock
async def test_send_chat_message_skips_empty_data_lines():
    sse_body = (
        "data: Risposta utile\n\n"
        "data: \n\n"
        "data: Altra risposta\n\n"
    )
    respx.post(f"{BACKEND_URL}/api/chat/message").mock(
        return_value=httpx.Response(
            200,
            content=sse_body.encode(),
            headers={"content-type": "text/event-stream"},
        )
    )

    result = await send_chat_message(
        message="test",
        backend_url=BACKEND_URL,
        password="changeme",
    )

    assert "Risposta utile" in result
    assert "Altra risposta" in result
    # empty data lines should not add blank entries
    assert result.count("\n\n") == 0 or "  " not in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd D:\Claude_Code\infraai\telegram_bot
python -m pytest tests/test_backend_client.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create `telegram_bot/backend_client.py`**

```python
import httpx


async def send_chat_message(
    message: str,
    backend_url: str,
    password: str,
) -> str:
    """Call the backend SSE chat endpoint and return the accumulated text."""
    url = f"{backend_url.rstrip('/')}/api/chat/message"
    headers = {"Authorization": f"Bearer {password}"}
    payload = {"message": message}

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                if response.status_code != 200:
                    return f"❌ Errore backend: HTTP {response.status_code}"

                chunks: list[str] = []
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        text = line[6:].strip()
                        if text:
                            chunks.append(text)

                return "\n".join(chunks) if chunks else "Nessuna risposta dal backend."
    except httpx.RequestError as exc:
        return f"❌ Errore di connessione al backend: {exc}"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd D:\Claude_Code\infraai\telegram_bot
python -m pytest tests/test_backend_client.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git -C D:\Claude_Code\infraai add telegram_bot/backend_client.py telegram_bot/tests/test_backend_client.py
git -C D:\Claude_Code\infraai commit -m "feat: backend client streams SSE chat responses and accumulates text"
```

---

### Task 6: Bot Handlers

Implements the Telegram `/silence` command handler and the natural language message handler. Tests use mock `Update`/`Context` objects — no real Telegram connection.

**Files:**
- Create: `telegram_bot/bot_handlers.py`
- Create: `telegram_bot/tests/test_bot_handlers.py`

- [ ] **Step 1: Write failing tests in `telegram_bot/tests/test_bot_handlers.py`**

```python
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Message, Update

from bot_handlers import handle_silence, handle_message


def make_update(text: str, args: list[str] | None = None) -> tuple[Update, MagicMock]:
    message = MagicMock(spec=Message)
    message.text = text
    message.reply_text = AsyncMock()

    update = MagicMock(spec=Update)
    update.message = message

    context = MagicMock()
    context.args = args or []
    return update, context


@pytest.mark.asyncio
async def test_silence_adds_two_hour_silence(db_session):
    update, context = make_update("/silence srv-01 2h", args=["srv-01", "2h"])

    with patch("bot_handlers.AsyncSessionLocal") as mock_factory:
        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=db_session)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        mock_factory.return_value = mock_cm

        await handle_silence(update, context)

    update.message.reply_text.assert_called_once()
    reply = update.message.reply_text.call_args[0][0]
    assert "srv-01" in reply
    assert "silenziat" in reply.lower()


@pytest.mark.asyncio
async def test_silence_requires_hostname(db_session):
    update, context = make_update("/silence", args=[])

    await handle_silence(update, context)

    update.message.reply_text.assert_called_once()
    reply = update.message.reply_text.call_args[0][0]
    assert "uso" in reply.lower() or "usage" in reply.lower() or "/silence" in reply


@pytest.mark.asyncio
async def test_silence_invalid_duration(db_session):
    update, context = make_update("/silence srv-01 xyz", args=["srv-01", "xyz"])

    await handle_silence(update, context)

    reply = update.message.reply_text.call_args[0][0]
    assert "durata" in reply.lower() or "formato" in reply.lower()


@pytest.mark.asyncio
async def test_handle_message_forwards_to_backend():
    update, context = make_update("aggiorna tutti i server del cliente Rossi")

    with patch("bot_handlers.send_chat_message", new=AsyncMock(return_value="✅ Completato")) as mock_send:
        await handle_message(update, context)

    mock_send.assert_awaited_once()
    update.message.reply_text.assert_called_once()
    reply = update.message.reply_text.call_args[0][0]
    assert "Completato" in reply


@pytest.mark.asyncio
async def test_handle_message_shows_typing_first():
    update, context = make_update("leggi log di nginx su srv-01")
    update.message.chat_id = 12345
    context.bot = AsyncMock()
    context.bot.send_chat_action = AsyncMock()

    with patch("bot_handlers.send_chat_message", new=AsyncMock(return_value="log output")):
        await handle_message(update, context)

    # Should have sent "typing" action before the reply
    context.bot.send_chat_action.assert_awaited()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd D:\Claude_Code\infraai\telegram_bot
python -m pytest tests/test_bot_handlers.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create `telegram_bot/bot_handlers.py`**

```python
import re
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from backend_client import send_chat_message
from config import settings
from db import AsyncSessionLocal
from silence import SilenceStore

# Pattern: "2h", "30m", "1d"
_DURATION_RE = re.compile(r"^(\d+)(h|m|d)$")


def _parse_duration(text: str) -> timedelta | None:
    match = _DURATION_RE.match(text.strip().lower())
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2)
    if unit == "h":
        return timedelta(hours=value)
    if unit == "m":
        return timedelta(minutes=value)
    if unit == "d":
        return timedelta(days=value)
    return None


async def handle_silence(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args or []

    if len(args) < 1:
        await update.message.reply_text(
            "Uso: /silence <hostname> [durata]\n"
            "Esempi: /silence srv-01 2h | /silence srv-01 30m | /silence srv-01 1d\n"
            "Senza durata: mostra stato silence attuale."
        )
        return

    hostname = args[0]

    if len(args) < 2:
        # Show current silence status
        async with AsyncSessionLocal() as session:
            store = SilenceStore(session)
            until = await store.get_silence(hostname)
        if until:
            await update.message.reply_text(
                f"🔕 {hostname} è silenziato fino alle {until.strftime('%H:%M %d/%m/%Y')} UTC"
            )
        else:
            await update.message.reply_text(f"🔔 {hostname} non è silenziato.")
        return

    duration = _parse_duration(args[1])
    if duration is None:
        await update.message.reply_text(
            f"Formato durata non valido: '{args[1]}'\n"
            "Usa: 2h (ore), 30m (minuti), 1d (giorno)"
        )
        return

    until = datetime.now(timezone.utc) + duration
    async with AsyncSessionLocal() as session:
        store = SilenceStore(session)
        await store.add(hostname=hostname, silenced_until=until)

    await update.message.reply_text(
        f"🔕 {hostname} silenziato per {args[1]} "
        f"(fino alle {until.strftime('%H:%M')} UTC)"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if not message or not message.text:
        return

    # Show typing indicator
    try:
        await context.bot.send_chat_action(
            chat_id=message.chat_id, action=ChatAction.TYPING
        )
    except Exception:
        pass

    result = await send_chat_message(
        message=message.text,
        backend_url=settings.backend_url,
        password=settings.auth_password,
    )

    # Telegram message max length is 4096 chars
    if len(result) > 4000:
        result = result[:4000] + "\n…(troncato)"

    await message.reply_text(result)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd D:\Claude_Code\infraai\telegram_bot
python -m pytest tests/test_bot_handlers.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git -C D:\Claude_Code\infraai add telegram_bot/bot_handlers.py telegram_bot/tests/test_bot_handlers.py
git -C D:\Claude_Code\infraai commit -m "feat: telegram bot handlers for /silence command and natural language forwarding"
```

---

### Task 7: Alert Dispatcher + APScheduler + Main Entry Point

Wires everything together: alert polling with deduplication, daily report, and the bot Application with handlers registered. Creates `main.py` as the entry point.

**Files:**
- Create: `telegram_bot/alert_dispatcher.py`
- Create: `telegram_bot/main.py`
- Create: `telegram_bot/tests/test_alert_dispatcher.py`

- [ ] **Step 1: Write failing tests in `telegram_bot/tests/test_alert_dispatcher.py`**

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alert_dispatcher import AlertDispatcher
from monitors import Alert, Severity


def make_alert(alert_id: str, hostname: str, severity: Severity) -> Alert:
    return Alert(
        alert_id=alert_id,
        hostname=hostname,
        description=f"Problem on {hostname}",
        severity=severity,
    )


@pytest.mark.asyncio
async def test_dispatcher_sends_new_alert():
    mock_bot = AsyncMock()
    dispatcher = AlertDispatcher(bot=mock_bot, chat_id="123")

    alert = make_alert("zabbix-101", "srv-01", Severity.CRITICAL)
    with patch("alert_dispatcher.ZabbixChecker") as MockZ, \
         patch("alert_dispatcher.KumaChecker") as MockK, \
         patch("alert_dispatcher.httpx.AsyncClient") as MockClient:

        mock_zabbix = AsyncMock()
        mock_zabbix.get_alerts = AsyncMock(return_value=[alert])
        MockZ.return_value = mock_zabbix

        mock_kuma = AsyncMock()
        mock_kuma.get_alerts = AsyncMock(return_value=[])
        MockK.return_value = mock_kuma

        mock_client_instance = AsyncMock()
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

        await dispatcher.check_and_send()

    mock_bot.send_message.assert_awaited_once()
    call_text = mock_bot.send_message.call_args.kwargs["text"]
    assert "srv-01" in call_text
    assert "CRITICAL" in call_text or "🔴" in call_text


@pytest.mark.asyncio
async def test_dispatcher_does_not_resend_same_alert():
    mock_bot = AsyncMock()
    dispatcher = AlertDispatcher(bot=mock_bot, chat_id="123")

    alert = make_alert("zabbix-101", "srv-01", Severity.CRITICAL)

    for _ in range(2):
        with patch("alert_dispatcher.ZabbixChecker") as MockZ, \
             patch("alert_dispatcher.KumaChecker") as MockK, \
             patch("alert_dispatcher.httpx.AsyncClient") as MockClient:

            mock_zabbix = AsyncMock()
            mock_zabbix.get_alerts = AsyncMock(return_value=[alert])
            MockZ.return_value = mock_zabbix
            mock_kuma = AsyncMock()
            mock_kuma.get_alerts = AsyncMock(return_value=[])
            MockK.return_value = mock_kuma
            mock_client_instance = AsyncMock()
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

            await dispatcher.check_and_send()

    # Should have sent only once despite two polls
    assert mock_bot.send_message.await_count == 1


@pytest.mark.asyncio
async def test_dispatcher_skips_silenced_hosts(db_session):
    from datetime import datetime, timedelta, timezone
    from silence import SilenceStore

    store = SilenceStore(db_session)
    await store.add("srv-silenced", datetime.now(timezone.utc) + timedelta(hours=1))

    mock_bot = AsyncMock()
    dispatcher = AlertDispatcher(bot=mock_bot, chat_id="123")

    alert = make_alert("zabbix-999", "srv-silenced", Severity.WARNING)

    with patch("alert_dispatcher.ZabbixChecker") as MockZ, \
         patch("alert_dispatcher.KumaChecker") as MockK, \
         patch("alert_dispatcher.httpx.AsyncClient") as MockClient, \
         patch("alert_dispatcher.AsyncSessionLocal") as MockFactory:

        mock_zabbix = AsyncMock()
        mock_zabbix.get_alerts = AsyncMock(return_value=[alert])
        MockZ.return_value = mock_zabbix
        mock_kuma = AsyncMock()
        mock_kuma.get_alerts = AsyncMock(return_value=[])
        MockK.return_value = mock_kuma
        mock_client_instance = AsyncMock()
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=None)

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=db_session)
        mock_cm.__aexit__ = AsyncMock(return_value=None)
        MockFactory.return_value = mock_cm

        await dispatcher.check_and_send()

    mock_bot.send_message.assert_not_awaited()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd D:\Claude_Code\infraai\telegram_bot
python -m pytest tests/test_alert_dispatcher.py -v
```

Expected: `ImportError: cannot import name 'AlertDispatcher'`

- [ ] **Step 3: Create `telegram_bot/alert_dispatcher.py`**

```python
import httpx
from telegram import Bot

from config import settings
from db import AsyncSessionLocal
from monitors import Alert, KumaChecker, Severity, ZabbixChecker
from silence import SilenceStore

_SEVERITY_EMOJI = {
    Severity.CRITICAL: "🔴",
    Severity.WARNING: "🟡",
    Severity.INFO: "🔵",
}


class AlertDispatcher:
    def __init__(self, bot: Bot, chat_id: str) -> None:
        self._bot = bot
        self._chat_id = chat_id
        # In-memory deduplication: alert_ids that have already been sent
        self._sent_ids: set[str] = set()

    async def check_and_send(self) -> None:
        zabbix = ZabbixChecker(url=settings.zabbix_url, token=settings.zabbix_token)
        kuma = KumaChecker(url=settings.kuma_url, api_key=settings.kuma_api_key)

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                zabbix_alerts = await zabbix.get_alerts(client)
            except Exception:
                zabbix_alerts = []
            try:
                kuma_alerts = await kuma.get_alerts(client)
            except Exception:
                kuma_alerts = []

        all_alerts = zabbix_alerts + kuma_alerts
        current_ids = {a.alert_id for a in all_alerts}

        # Remove resolved alerts from sent set
        self._sent_ids &= current_ids

        for alert in all_alerts:
            if alert.alert_id in self._sent_ids:
                continue

            if await self._is_silenced(alert.hostname):
                continue

            await self._send_alert(alert)
            self._sent_ids.add(alert.alert_id)

    async def _is_silenced(self, hostname: str) -> bool:
        async with AsyncSessionLocal() as session:
            store = SilenceStore(session)
            return await store.is_silenced(hostname)

    async def _send_alert(self, alert: Alert) -> None:
        emoji = _SEVERITY_EMOJI.get(alert.severity, "⚠️")
        text = (
            f"{emoji} {alert.severity.value}\n"
            f"Host: {alert.hostname}\n"
            f"{alert.description}"
        )
        await self._bot.send_message(chat_id=self._chat_id, text=text)

    async def send_daily_report(self) -> None:
        """Send a summary report. Called by APScheduler at 08:00."""
        from sqlalchemy import func, select
        from db import AsyncSessionLocal as session_factory

        # Count active servers from the shared DB
        try:
            async with session_factory() as session:
                from sqlalchemy import text
                result = await session.execute(
                    text("SELECT COUNT(*) FROM servers WHERE is_active = true")
                )
                server_count = result.scalar_one()
        except Exception:
            server_count = "N/A"

        text = (
            f"🔵 Report giornaliero InfraAI\n"
            f"Server attivi: {server_count}\n"
            f"Alert attivi: {len(self._sent_ids)}"
        )
        await self._bot.send_message(chat_id=self._chat_id, text=text)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd D:\Claude_Code\infraai\telegram_bot
python -m pytest tests/test_alert_dispatcher.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Create `telegram_bot/main.py`**

```python
import asyncio
import datetime
import logging

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from alert_dispatcher import AlertDispatcher
from bot_handlers import handle_message, handle_silence
from config import settings

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)


async def main() -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN non configurato in .env")
    if not settings.telegram_chat_id:
        raise RuntimeError("TELEGRAM_CHAT_ID non configurato in .env")

    app = ApplicationBuilder().token(settings.telegram_bot_token).build()

    # Command and message handlers
    app.add_handler(CommandHandler("silence", handle_silence))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Alert dispatcher (uses the bot inside ApplicationBuilder)
    dispatcher = AlertDispatcher(bot=app.bot, chat_id=settings.telegram_chat_id)

    # Schedule alert polling every 5 minutes, starting after 30s
    app.job_queue.run_repeating(
        lambda ctx: asyncio.ensure_future(dispatcher.check_and_send()),
        interval=300,
        first=30,
    )

    # Schedule daily report at 08:00 UTC
    app.job_queue.run_daily(
        lambda ctx: asyncio.ensure_future(dispatcher.send_daily_report()),
        time=datetime.time(8, 0, 0, tzinfo=datetime.timezone.utc),
    )

    logging.info("InfraAI Telegram Bot avviato.")
    async with app:
        await app.start()
        await app.updater.start_polling()
        await asyncio.Event().wait()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 6: Run the full telegram_bot test suite**

```bash
cd D:\Claude_Code\infraai\telegram_bot
python -m pytest -v
```

Expected: all tests pass (13+ tests).

- [ ] **Step 7: Commit**

```bash
git -C D:\Claude_Code\infraai add telegram_bot/alert_dispatcher.py telegram_bot/main.py telegram_bot/tests/test_alert_dispatcher.py
git -C D:\Claude_Code\infraai commit -m "feat: alert dispatcher with deduplication, daily report, bot main entry point"
```

---

## Self-Review

**Spec coverage check (from `2026-05-09-infraai-design.md`):**

| Requisito spec | Task |
|---|---|
| Alert CRITICAL 🔴: server down, disco >95%, DB giù, SSL scaduto → Immediato | Task 4 (ZabbixChecker priority≥4→CRITICAL), Task 7 (AlertDispatcher) |
| Alert WARNING 🟡: CPU >85%, RAM >90%, disco >80%, SSL <7gg → entro 5 min | Task 4 (priority 2-3→WARNING), Task 7 (polling ogni 5min) |
| Alert INFO 🔵: report giornaliero ore 08:00 | Task 7 (job_queue.run_daily at 08:00 UTC) |
| Silenziamento: `/silence srv-01 2h` | Task 3 (SilenceStore), Task 6 (handle_silence) |
| Risposta al bot per comandi rapidi (es. `riavvia nginx su srv-01`) | Task 5 (backend_client), Task 6 (handle_message) |
| Alert con dettaglio: hostname, metrica, valore attuale | Task 7 (AlertDispatcher._send_alert con hostname + description) |
| Tutte le soglie configurabili via file | ✅ config.py + .env |
| python-telegram-bot | ✅ requirements.txt |

**Soglie Zabbix:** La spec parla di soglie specifiche (CPU >85%, disco >95%). Queste sono configurate **in Zabbix** come trigger, non nel bot — il bot riceve i trigger già attivati. Corretto design.

**Placeholder scan:** Nessun TBD o TODO nel piano. Tutti i blocchi di codice sono completi.

**Type consistency:**
- `Alert.alert_id` usato in Task 4 e Task 7 ✅
- `SilenceStore.add/is_silenced/get_silence/clear_expired` usati in Task 3, 6, 7 ✅
- `AlertDispatcher(bot, chat_id)` usato in Task 7 test e main.py ✅
- `send_chat_message(message, backend_url, password)` usato in Task 5 e Task 6 ✅
