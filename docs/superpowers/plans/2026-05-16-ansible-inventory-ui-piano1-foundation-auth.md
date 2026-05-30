# ansible-inventory-ui — Piano 1: Foundation + Auth + Server CRUD

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Costruire il backend completo: infrastruttura Docker Compose, schema PostgreSQL, autenticazione JWT con TOTP (Google Authenticator), gestione utenti con ruoli (Viewer/Editor/Admin) e CRUD server con duplicate detection.

**Architecture:** FastAPI + SQLAlchemy 2.0 async. Auth a due step: password → pre-auth token (5 min) → TOTP verify → JWT completo (8h). TOTP via pyotp, QR code per setup. Server CRUD con controllo duplicati sia su DB locale. Nessun AWX né frontend in questo piano — API REST testabile via Swagger UI.

**Tech Stack:** Python 3.12, FastAPI 0.115, SQLAlchemy 2.0 + asyncpg, Alembic, python-jose (JWT), passlib[bcrypt], pyotp, qrcode, pytest + pytest-asyncio + httpx, Docker Compose, PostgreSQL 16

---

## Struttura file

```
ansible-inventory-ui/
├── backend/
│   ├── main.py                        # FastAPI app + router registration
│   ├── config.py                      # Settings via pydantic-settings
│   ├── database.py                    # Async SQLAlchemy engine + session
│   ├── pytest.ini                     # Test config + PYTHONPATH
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py                    # User model (ruoli, TOTP fields)
│   │   ├── server.py                  # Server model (tutti i campi Airtable)
│   │   └── audit.py                   # AuditLog model
│   ├── core/
│   │   ├── __init__.py
│   │   └── security.py                # JWT, bcrypt, TOTP utils
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py                    # Dependency: get_current_user, require_role
│   │   ├── auth.py                    # Login, TOTP verify, /me
│   │   ├── users.py                   # CRUD utenti + TOTP setup (Admin)
│   │   └── servers.py                 # CRUD server + duplicate check
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py                # DB in-memory, AsyncClient fixture
│   │   ├── test_security.py           # JWT, bcrypt, TOTP utils
│   │   ├── test_auth.py               # Login flow, TOTP verify
│   │   ├── test_users.py              # CRUD utenti, TOTP setup
│   │   └── test_servers.py            # CRUD server, duplicate check
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
└── init.sh                            # Crea primo utente Admin
```

---

### Task 1: Project Foundation

**Files:**
- Create: `ansible-inventory-ui/backend/requirements.txt`
- Create: `ansible-inventory-ui/backend/requirements-dev.txt`
- Create: `ansible-inventory-ui/backend/pytest.ini`
- Create: `ansible-inventory-ui/.env.example`
- Create: `ansible-inventory-ui/backend/config.py`
- Create: `ansible-inventory-ui/backend/database.py`
- Create: `ansible-inventory-ui/backend/main.py`
- Create: `ansible-inventory-ui/backend/Dockerfile`
- Create: `ansible-inventory-ui/docker-compose.yml`
- Create: `ansible-inventory-ui/.gitignore`

- [ ] **Step 1: Crea la struttura di directory**

```bash
mkdir -p ansible-inventory-ui/backend/models \
         ansible-inventory-ui/backend/core \
         ansible-inventory-ui/backend/api \
         ansible-inventory-ui/backend/tests \
         ansible-inventory-ui/backend/alembic/versions \
         ansible-inventory-ui/nginx
touch ansible-inventory-ui/backend/models/__init__.py
touch ansible-inventory-ui/backend/core/__init__.py
touch ansible-inventory-ui/backend/api/__init__.py
touch ansible-inventory-ui/backend/tests/__init__.py
cd ansible-inventory-ui && git init
```

- [ ] **Step 2: Crea `backend/requirements.txt`**

```
fastapi==0.115.5
uvicorn[standard]==0.32.1
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
alembic==1.14.0
pydantic-settings==2.6.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
pyotp==2.9.0
qrcode==7.4.2
python-multipart==0.0.17
```

- [ ] **Step 3: Crea `backend/requirements-dev.txt`**

```
pytest==8.3.3
pytest-asyncio==0.24.0
pytest-cov==6.0.0
httpx==0.28.0
aiosqlite==0.20.0
```

- [ ] **Step 4: Crea `backend/pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
pythonpath = .
```

- [ ] **Step 5: Crea `.env.example`**

```env
# Database
DATABASE_URL=postgresql+asyncpg://invui:invui@db:5432/invui

# Auth
JWT_SECRET=change-me-very-long-random-string-min-32-chars
JWT_EXPIRE_HOURS=8

# AWX (Piano 2)
AWX_URL=https://your-awx-server
AWX_TOKEN=your-awx-api-token

# Airtable (Piano 2)
AIRTABLE_API_TOKEN=your-airtable-token
AIRTABLE_BASE_ID=your-base-id
AIRTABLE_TABLE_NAME=Servers

# Security (opzionale: whitelist IP in nginx)
ALLOWED_IPS=1.2.3.4,5.6.7.8
```

- [ ] **Step 6: Crea `backend/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://invui:invui@db:5432/invui"
    jwt_secret: str = "change-me-very-long-random-string-min-32-chars"
    jwt_expire_hours: int = 8
    awx_url: str = ""
    awx_token: str = ""
    airtable_api_token: str = ""
    airtable_base_id: str = ""
    airtable_table_name: str = "Servers"
    allowed_ips: str = ""


settings = Settings()
```

- [ ] **Step 7: Crea `backend/database.py`**

```python
from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from config import settings


engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 8: Crea `backend/main.py`**

```python
from fastapi import FastAPI

app = FastAPI(title="ansible-inventory-ui", version="1.0.0")


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 9: Crea `backend/Dockerfile`**

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 10: Crea `docker-compose.yml`**

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: invui
      POSTGRES_PASSWORD: invui
      POSTGRES_DB: invui
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U invui"]
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

- [ ] **Step 11: Crea `.gitignore`**

```
.env
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
.venv/
node_modules/
.next/
```

- [ ] **Step 12: Installa dipendenze in locale**

```bash
cd ansible-inventory-ui/backend
pip install -r requirements.txt -r requirements-dev.txt
```

- [ ] **Step 13: Copia `.env.example` in `.env` e inserisci i valori**

```bash
cd ansible-inventory-ui
cp .env.example .env
# Edita .env con un JWT_SECRET reale (es. openssl rand -hex 32)
```

- [ ] **Step 14: Commit**

```bash
cd ansible-inventory-ui
git add .
git commit -m "feat: project foundation — docker-compose, config, fastapi skeleton"
```

---

### Task 2: Database Models + Migrations

**Files:**
- Create: `backend/models/user.py`
- Create: `backend/models/server.py`
- Create: `backend/models/audit.py`
- Modify: `backend/models/__init__.py`
- Create: `backend/alembic/env.py` (sovrascrive quello generato)
- Create: `backend/alembic.ini` (generato da alembic)

- [ ] **Step 1: Crea `backend/models/user.py`**

```python
import enum
from datetime import datetime
from sqlalchemy import String, Enum as SAEnum, DateTime, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class UserRole(str, enum.Enum):
    viewer = "viewer"
    editor = "editor"
    admin = "admin"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.viewer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    totp_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_backup_codes: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array di hash
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 2: Crea `backend/models/server.py`**

```python
import enum
from datetime import datetime
from sqlalchemy import String, Enum as SAEnum, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class Ambiente(str, enum.Enum):
    produzione = "Produzione"
    sviluppo = "Sviluppo"
    staging = "Staging"
    test = "Test"


class TipoAsset(str, enum.Enum):
    server_dedicato = "Server Dedicato"
    vps = "VPS"
    macchina_virtuale = "Macchina Virtuale"


class SistemaOperativo(str, enum.Enum):
    linux = "Linux"
    windows = "Windows"


class Hypervisor(str, enum.Enum):
    proxmox = "Proxmox"
    vmware_esxi = "VMware ESXi"
    hyper_v = "Hyper-V"
    nessuno = "Nessuno"


class Server(Base):
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(primary_key=True)
    hostname: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    fqdn: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip: Mapped[str] = mapped_column(String(45))
    nome_cliente: Mapped[str | None] = mapped_column(String(255), nullable=True)
    codice_cliente: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ambiente: Mapped[Ambiente | None] = mapped_column(SAEnum(Ambiente), nullable=True)
    tipo_asset: Mapped[TipoAsset | None] = mapped_column(SAEnum(TipoAsset), nullable=True)
    sistema_operativo: Mapped[SistemaOperativo | None] = mapped_column(SAEnum(SistemaOperativo), nullable=True)
    distribuzione_os: Mapped[str | None] = mapped_column(String(100), nullable=True)
    versione_os: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hypervisor: Mapped[Hypervisor | None] = mapped_column(SAEnum(Hypervisor), nullable=True)
    cluster_hypervisor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    awx_inventory_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    awx_host_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    airtable_record_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
```

- [ ] **Step 3: Crea `backend/models/audit.py`**

```python
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(50))
    server_hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 4: Aggiorna `backend/models/__init__.py`**

```python
from .user import User, UserRole
from .server import Server, Ambiente, TipoAsset, SistemaOperativo, Hypervisor
from .audit import AuditLog

__all__ = [
    "User", "UserRole",
    "Server", "Ambiente", "TipoAsset", "SistemaOperativo", "Hypervisor",
    "AuditLog",
]
```

- [ ] **Step 5: Inizializza Alembic**

```bash
cd ansible-inventory-ui/backend
alembic init alembic
```

Expected: crea `alembic/` directory e `alembic.ini`

- [ ] **Step 6: Sostituisci `backend/alembic/env.py`**

```python
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from config import settings
from database import Base
import models  # noqa: F401

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
cd ansible-inventory-ui/backend
alembic revision --autogenerate -m "initial schema"
```

Expected: crea `alembic/versions/xxxx_initial_schema.py` con le tabelle `users`, `servers`, `audit_log`

- [ ] **Step 8: Avvia PostgreSQL e applica la migration**

```bash
cd ansible-inventory-ui
docker compose up db -d
# Attendi ~5 secondi
cd backend
DATABASE_URL=postgresql+asyncpg://invui:invui@localhost:5432/invui alembic upgrade head
```

Expected: `Running upgrade -> xxxx, initial schema`

- [ ] **Step 9: Commit**

```bash
cd ansible-inventory-ui
git add backend/models/ backend/alembic/ backend/alembic.ini
git commit -m "feat: database models — User, Server, AuditLog + alembic migrations"
```

---

### Task 3: Security Core (JWT + bcrypt + TOTP)

**Files:**
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_security.py`
- Create: `backend/core/security.py`

- [ ] **Step 1: Crea `backend/tests/conftest.py`**

```python
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from database import Base, get_db
from main import app
import models  # noqa

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Crea `backend/tests/test_security.py`**

```python
import pytest
from core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    generate_totp_secret,
    verify_totp,
    generate_backup_codes,
    hash_backup_codes,
    verify_backup_code,
)


def test_hash_and_verify_password():
    hashed = hash_password("mysecret")
    assert hashed != "mysecret"
    assert verify_password("mysecret", hashed)
    assert not verify_password("wrong", hashed)


def test_create_and_decode_access_token():
    token = create_access_token({"sub": "alice", "role": "editor"})
    data = decode_access_token(token)
    assert data["sub"] == "alice"
    assert data["role"] == "editor"


def test_decode_invalid_token_raises():
    from jose import JWTError
    with pytest.raises(JWTError):
        decode_access_token("not.a.valid.token")


def test_totp_verify_valid_code():
    secret = generate_totp_secret()
    import pyotp
    code = pyotp.TOTP(secret).now()
    assert verify_totp(secret, code)


def test_totp_verify_wrong_code():
    secret = generate_totp_secret()
    assert not verify_totp(secret, "000000")


def test_backup_codes_flow():
    codes = generate_backup_codes(8)
    assert len(codes) == 8
    hashed = hash_backup_codes(codes)
    matched, remaining = verify_backup_code(codes[0], hashed)
    assert matched
    assert len(remaining) == 7
    matched2, _ = verify_backup_code(codes[0], remaining)
    assert not matched2  # codice già usato, non è più nella lista
```

- [ ] **Step 3: Esegui i test — verifica che falliscono**

```bash
cd ansible-inventory-ui/backend
pytest tests/test_security.py -v
```

Expected: `FAILED ... ModuleNotFoundError: No module named 'core.security'`

- [ ] **Step 4: Crea `backend/core/security.py`**

```python
import base64
import io
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import pyotp
import qrcode
from jose import jwt
from passlib.context import CryptContext

from config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict[str, Any], expire_minutes: int | None = None) -> str:
    to_encode = data.copy()
    minutes = expire_minutes if expire_minutes is not None else settings.jwt_expire_hours * 60
    to_encode["exp"] = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def get_totp_qr_base64(secret: str, username: str) -> str:
    uri = pyotp.TOTP(secret).provisioning_uri(
        name=username, issuer_name="ansible-inventory-ui"
    )
    buf = io.BytesIO()
    qrcode.make(uri).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def verify_totp(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def generate_backup_codes(n: int = 8) -> list[str]:
    return [secrets.token_hex(4).upper() for _ in range(n)]


def hash_backup_codes(codes: list[str]) -> list[str]:
    return [pwd_context.hash(c) for c in codes]


def verify_backup_code(code: str, hashed_codes: list[str]) -> tuple[bool, list[str]]:
    for i, hashed in enumerate(hashed_codes):
        if pwd_context.verify(code.upper(), hashed):
            return True, hashed_codes[:i] + hashed_codes[i + 1:]
    return False, hashed_codes
```

- [ ] **Step 5: Esegui i test — verifica che passano**

```bash
cd ansible-inventory-ui/backend
pytest tests/test_security.py -v
```

Expected: `6 passed`

- [ ] **Step 6: Commit**

```bash
cd ansible-inventory-ui
git add backend/core/security.py backend/tests/
git commit -m "feat: security core — JWT, bcrypt, TOTP, backup codes"
```

---

### Task 4: Auth Endpoints (Login + TOTP Verify)

Il login avviene in due step quando il TOTP è abilitato:
1. `POST /api/auth/login` → password ok, TOTP abilitato → `{"requires_totp": true, "pre_auth_token": "..."}`
2. `POST /api/auth/verify-totp` → `{pre_auth_token, code}` → `{"access_token": "..."}`

Se TOTP non è abilitato, il passo 1 restituisce direttamente l'`access_token`.

**Files:**
- Create: `backend/api/deps.py`
- Create: `backend/tests/test_auth.py`
- Create: `backend/api/auth.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Crea `backend/api/deps.py`**

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError
from database import get_db
from models.user import User, UserRole
from core.security import decode_access_token

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
```

- [ ] **Step 2: Crea `backend/tests/test_auth.py`**

```python
import json
import pytest
import pyotp
from sqlalchemy import select
from models.user import User, UserRole
from core.security import hash_password, generate_totp_secret, hash_backup_codes, generate_backup_codes


async def _create_user(db, username="alice", role=UserRole.editor, totp=False):
    secret = generate_totp_secret() if totp else None
    backup_codes = json.dumps(hash_backup_codes(generate_backup_codes())) if totp else None
    user = User(
        username=username,
        email=f"{username}@example.com",
        hashed_password=hash_password("password123"),
        role=role,
        is_active=True,
        totp_secret=secret,
        totp_enabled=totp,
        totp_backup_codes=backup_codes,
    )
    db.add(user)
    await db.commit()
    return user


@pytest.mark.asyncio
async def test_login_no_totp_returns_access_token(client, db_session):
    await _create_user(db_session, totp=False)
    resp = await client.post("/api/auth/login", json={"username": "alice", "password": "password123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data.get("requires_totp") is not True


@pytest.mark.asyncio
async def test_login_with_totp_returns_pre_auth_token(client, db_session):
    await _create_user(db_session, totp=True)
    resp = await client.post("/api/auth/login", json={"username": "alice", "password": "password123"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["requires_totp"] is True
    assert "pre_auth_token" in data
    assert "access_token" not in data


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client, db_session):
    await _create_user(db_session, totp=False)
    resp = await client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user_returns_401(client, db_session):
    user = await _create_user(db_session, totp=False)
    user.is_active = False
    await db_session.commit()
    resp = await client.post("/api/auth/login", json={"username": "alice", "password": "password123"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_verify_totp_valid_code_returns_access_token(client, db_session):
    user = await _create_user(db_session, totp=True)
    login = await client.post("/api/auth/login", json={"username": "alice", "password": "password123"})
    pre_auth_token = login.json()["pre_auth_token"]
    code = pyotp.TOTP(user.totp_secret).now()
    resp = await client.post("/api/auth/verify-totp", json={"pre_auth_token": pre_auth_token, "code": code})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_verify_totp_wrong_code_returns_401(client, db_session):
    await _create_user(db_session, totp=True)
    login = await client.post("/api/auth/login", json={"username": "alice", "password": "password123"})
    pre_auth_token = login.json()["pre_auth_token"]
    resp = await client.post("/api/auth/verify-totp", json={"pre_auth_token": pre_auth_token, "code": "000000"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_verify_totp_backup_code_works(client, db_session):
    raw_codes = generate_backup_codes(8)
    secret = generate_totp_secret()
    user = User(
        username="bob", email="bob@example.com",
        hashed_password=hash_password("password123"),
        role=UserRole.editor, is_active=True,
        totp_secret=secret, totp_enabled=True,
        totp_backup_codes=json.dumps(hash_backup_codes(raw_codes)),
    )
    db_session.add(user)
    await db_session.commit()
    login = await client.post("/api/auth/login", json={"username": "bob", "password": "password123"})
    pre_auth_token = login.json()["pre_auth_token"]
    resp = await client.post("/api/auth/verify-totp", json={"pre_auth_token": pre_auth_token, "code": raw_codes[0]})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_me_returns_current_user(client, db_session):
    await _create_user(db_session, totp=False)
    login = await client.post("/api/auth/login", json={"username": "alice", "password": "password123"})
    token = login.json()["access_token"]
    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "alice"
```

- [ ] **Step 3: Esegui i test — verifica che falliscono**

```bash
cd ansible-inventory-ui/backend
pytest tests/test_auth.py -v
```

Expected: `FAILED ... 404 Not Found` (router non ancora registrato)

- [ ] **Step 4: Crea `backend/api/auth.py`**

```python
import json
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError
from database import get_db
from models.user import User
from core.security import (
    verify_password,
    create_access_token,
    decode_access_token,
    verify_totp,
    verify_backup_code,
)
from api.deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class VerifyTotpRequest(BaseModel):
    pre_auth_token: str
    code: str


@router.post("/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if not user or not user.is_active or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenziali non valide")

    if user.totp_enabled:
        pre_auth_token = create_access_token(
            {"sub": user.username, "type": "pre_auth"}, expire_minutes=5
        )
        return {"requires_totp": True, "pre_auth_token": pre_auth_token}

    token = create_access_token({"sub": user.username, "role": user.role})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/verify-totp")
async def verify_totp_endpoint(body: VerifyTotpRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_access_token(body.pre_auth_token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token non valido")

    if payload.get("type") != "pre_auth":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token non valido")

    result = await db.execute(select(User).where(User.username == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Utente non trovato")

    # Prova prima il codice TOTP
    if user.totp_secret and verify_totp(user.totp_secret, body.code):
        token = create_access_token({"sub": user.username, "role": user.role})
        return {"access_token": token, "token_type": "bearer"}

    # Poi prova i codici di backup
    if user.totp_backup_codes:
        hashed_codes = json.loads(user.totp_backup_codes)
        matched, remaining = verify_backup_code(body.code, hashed_codes)
        if matched:
            user.totp_backup_codes = json.dumps(remaining)
            await db.commit()
            token = create_access_token({"sub": user.username, "role": user.role})
            return {"access_token": token, "token_type": "bearer"}

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Codice non valido")


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "totp_enabled": current_user.totp_enabled,
    }
```

- [ ] **Step 5: Aggiorna `backend/main.py`**

```python
from fastapi import FastAPI
from api.auth import router as auth_router

app = FastAPI(title="ansible-inventory-ui", version="1.0.0")

app.include_router(auth_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Esegui i test — verifica che passano**

```bash
cd ansible-inventory-ui/backend
pytest tests/test_auth.py -v
```

Expected: `8 passed`

- [ ] **Step 7: Commit**

```bash
cd ansible-inventory-ui
git add backend/api/ backend/tests/test_auth.py backend/main.py
git commit -m "feat: auth endpoints — login, TOTP verify, /me"
```

---

### Task 5: User Management API (Admin)

**Files:**
- Create: `backend/tests/test_users.py`
- Create: `backend/api/users.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Crea `backend/tests/test_users.py`**

```python
import json
import pytest
from models.user import User, UserRole
from core.security import hash_password, generate_totp_secret, hash_backup_codes, generate_backup_codes


async def _create_admin(db):
    user = User(
        username="admin", email="admin@example.com",
        hashed_password=hash_password("adminpass"),
        role=UserRole.admin, is_active=True,
    )
    db.add(user)
    await db.commit()
    return user


async def _get_token(client, username="admin", password="adminpass"):
    resp = await client.post("/api/auth/login", json={"username": username, "password": password})
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_admin_can_create_user(client, db_session):
    await _create_admin(db_session)
    token = await _get_token(client)
    resp = await client.post(
        "/api/users/",
        json={"username": "newuser", "email": "new@example.com", "password": "pass1234", "role": "editor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    assert resp.json()["username"] == "newuser"


@pytest.mark.asyncio
async def test_non_admin_cannot_create_user(client, db_session):
    viewer = User(
        username="viewer", email="viewer@example.com",
        hashed_password=hash_password("pass"),
        role=UserRole.viewer, is_active=True,
    )
    db_session.add(viewer)
    await db_session.commit()
    token = await _get_token(client, "viewer", "pass")
    resp = await client.post(
        "/api/users/",
        json={"username": "x", "email": "x@x.com", "password": "pass", "role": "viewer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_list_users(client, db_session):
    await _create_admin(db_session)
    token = await _get_token(client)
    resp = await client.get("/api/users/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_admin_can_update_user_role(client, db_session):
    await _create_admin(db_session)
    token = await _get_token(client)
    create = await client.post(
        "/api/users/",
        json={"username": "u2", "email": "u2@example.com", "password": "pass1234", "role": "viewer"},
        headers={"Authorization": f"Bearer {token}"},
    )
    user_id = create.json()["id"]
    resp = await client.patch(
        f"/api/users/{user_id}",
        json={"role": "editor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "editor"


@pytest.mark.asyncio
async def test_setup_totp_returns_qr(client, db_session):
    await _create_admin(db_session)
    token = await _get_token(client)
    create = await client.post(
        "/api/users/",
        json={"username": "u3", "email": "u3@example.com", "password": "pass1234", "role": "editor"},
        headers={"Authorization": f"Bearer {token}"},
    )
    user_id = create.json()["id"]
    resp = await client.post(
        f"/api/users/{user_id}/totp/setup",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "qr_code_base64" in data
    assert "backup_codes" in data
    assert len(data["backup_codes"]) == 8
```

- [ ] **Step 2: Esegui i test — verifica che falliscono**

```bash
cd ansible-inventory-ui/backend
pytest tests/test_users.py -v
```

Expected: `FAILED ... 404 Not Found`

- [ ] **Step 3: Crea `backend/api/users.py`**

```python
import json
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models.user import User, UserRole
from core.security import (
    hash_password,
    generate_totp_secret,
    get_totp_qr_base64,
    generate_backup_codes,
    hash_backup_codes,
)
from api.deps import require_role

router = APIRouter(prefix="/api/users", tags=["users"])
_admin = require_role(UserRole.admin)


class CreateUserRequest(BaseModel):
    username: str
    email: str
    password: str
    role: UserRole = UserRole.viewer


class UpdateUserRequest(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None


def _user_out(u: User) -> dict:
    return {
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "role": u.role,
        "is_active": u.is_active,
        "totp_enabled": u.totp_enabled,
    }


@router.get("/")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_admin),
):
    result = await db.execute(select(User))
    return [_user_out(u) for u in result.scalars().all()]


@router.post("/", status_code=201)
async def create_user(
    body: CreateUserRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_admin),
):
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username già in uso")
    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return _user_out(user)


@router.patch("/{user_id}")
async def update_user(
    user_id: int,
    body: UpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    await db.commit()
    await db.refresh(user)
    return _user_out(user)


@router.post("/{user_id}/totp/setup")
async def setup_totp(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    secret = generate_totp_secret()
    raw_codes = generate_backup_codes(8)
    user.totp_secret = secret
    user.totp_enabled = True
    user.totp_backup_codes = json.dumps(hash_backup_codes(raw_codes))
    await db.commit()
    return {
        "qr_code_base64": get_totp_qr_base64(secret, user.username),
        "backup_codes": raw_codes,
    }


@router.delete("/{user_id}/totp")
async def disable_totp(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Utente non trovato")
    user.totp_secret = None
    user.totp_enabled = False
    user.totp_backup_codes = None
    await db.commit()
    return {"totp_enabled": False}
```

- [ ] **Step 4: Aggiorna `backend/main.py`**

```python
from fastapi import FastAPI
from api.auth import router as auth_router
from api.users import router as users_router

app = FastAPI(title="ansible-inventory-ui", version="1.0.0")

app.include_router(auth_router)
app.include_router(users_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Esegui i test — verifica che passano**

```bash
cd ansible-inventory-ui/backend
pytest tests/test_users.py -v
```

Expected: `5 passed`

- [ ] **Step 6: Commit**

```bash
cd ansible-inventory-ui
git add backend/api/users.py backend/tests/test_users.py backend/main.py
git commit -m "feat: user management API — CRUD, TOTP setup/disable (Admin only)"
```

---

### Task 6: Server CRUD + Duplicate Check

**Files:**
- Create: `backend/tests/test_servers.py`
- Create: `backend/api/servers.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Crea `backend/tests/test_servers.py`**

```python
import pytest
from models.user import User, UserRole
from models.server import Server, Ambiente, TipoAsset, SistemaOperativo, Hypervisor
from core.security import hash_password


async def _create_user(db, role=UserRole.editor):
    user = User(
        username="testuser", email="test@example.com",
        hashed_password=hash_password("pass"),
        role=role, is_active=True,
    )
    db.add(user)
    await db.commit()
    return user


async def _get_token(client, username="testuser", password="pass"):
    resp = await client.post("/api/auth/login", json={"username": username, "password": password})
    return resp.json()["access_token"]


SERVER_PAYLOAD = {
    "hostname": "srv-test-01",
    "ip": "192.168.1.10",
    "nome_cliente": "Acme Srl",
    "codice_cliente": "CL099",
    "ambiente": "Produzione",
    "tipo_asset": "VPS",
    "sistema_operativo": "Linux",
    "distribuzione_os": "Ubuntu Server",
    "versione_os": "22.04 LTS",
    "hypervisor": "Nessuno",
}


@pytest.mark.asyncio
async def test_editor_can_create_server(client, db_session):
    await _create_user(db_session, UserRole.editor)
    token = await _get_token(client)
    resp = await client.post("/api/servers/", json=SERVER_PAYLOAD,
                              headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 201
    assert resp.json()["hostname"] == "srv-test-01"


@pytest.mark.asyncio
async def test_viewer_cannot_create_server(client, db_session):
    await _create_user(db_session, UserRole.viewer)
    token = await _get_token(client)
    resp = await client.post("/api/servers/", json=SERVER_PAYLOAD,
                              headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_servers(client, db_session):
    await _create_user(db_session, UserRole.viewer)
    token = await _get_token(client)
    resp = await client.get("/api/servers/", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_create_duplicate_hostname_returns_409(client, db_session):
    await _create_user(db_session, UserRole.editor)
    token = await _get_token(client)
    await client.post("/api/servers/", json=SERVER_PAYLOAD,
                      headers={"Authorization": f"Bearer {token}"})
    resp = await client.post("/api/servers/", json=SERVER_PAYLOAD,
                              headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_check_duplicate_returns_available(client, db_session):
    await _create_user(db_session, UserRole.editor)
    token = await _get_token(client)
    resp = await client.get("/api/servers/check-duplicate?hostname=srv-new-99",
                             headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["available"] is True


@pytest.mark.asyncio
async def test_check_duplicate_returns_not_available(client, db_session):
    await _create_user(db_session, UserRole.editor)
    token = await _get_token(client)
    await client.post("/api/servers/", json=SERVER_PAYLOAD,
                      headers={"Authorization": f"Bearer {token}"})
    resp = await client.get("/api/servers/check-duplicate?hostname=srv-test-01",
                             headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["available"] is False
    assert "existing" in resp.json()


@pytest.mark.asyncio
async def test_editor_can_update_server(client, db_session):
    await _create_user(db_session, UserRole.editor)
    token = await _get_token(client)
    create = await client.post("/api/servers/", json=SERVER_PAYLOAD,
                                headers={"Authorization": f"Bearer {token}"})
    server_id = create.json()["id"]
    resp = await client.patch(
        f"/api/servers/{server_id}",
        json={"versione_os": "24.04 LTS"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["versione_os"] == "24.04 LTS"


@pytest.mark.asyncio
async def test_admin_can_delete_server(client, db_session):
    admin = User(
        username="admin", email="admin@example.com",
        hashed_password=hash_password("adminpass"),
        role=UserRole.admin, is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()
    token = await _get_token(client, "admin", "adminpass")
    create = await client.post("/api/servers/", json=SERVER_PAYLOAD,
                                headers={"Authorization": f"Bearer {token}"})
    server_id = create.json()["id"]
    resp = await client.delete(f"/api/servers/{server_id}",
                                headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_editor_cannot_delete_server(client, db_session):
    await _create_user(db_session, UserRole.editor)
    token = await _get_token(client)
    create = await client.post("/api/servers/", json=SERVER_PAYLOAD,
                                headers={"Authorization": f"Bearer {token}"})
    server_id = create.json()["id"]
    resp = await client.delete(f"/api/servers/{server_id}",
                                headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
```

- [ ] **Step 2: Esegui i test — verifica che falliscono**

```bash
cd ansible-inventory-ui/backend
pytest tests/test_servers.py -v
```

Expected: `FAILED ... 404 Not Found`

- [ ] **Step 3: Crea `backend/api/servers.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db
from models.server import Server, Ambiente, TipoAsset, SistemaOperativo, Hypervisor
from models.user import User, UserRole
from api.deps import get_current_user, require_role

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
):
    existing = await db.execute(select(Server).where(Server.hostname == body.hostname))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Hostname '{body.hostname}' già presente")
    server = Server(**body.model_dump(), created_by=current_user.id)
    db.add(server)
    await db.commit()
    await db.refresh(server)
    return _server_out(server)


@router.patch("/{server_id}")
async def update_server(
    server_id: int,
    body: ServerUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_editor_plus),
):
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server non trovato")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(server, field, value)
    await db.commit()
    await db.refresh(server)
    return _server_out(server)


@router.delete("/{server_id}", status_code=204)
async def delete_server(
    server_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(_admin_only),
):
    result = await db.execute(select(Server).where(Server.id == server_id))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(status_code=404, detail="Server non trovato")
    await db.delete(server)
    await db.commit()
```

- [ ] **Step 4: Aggiorna `backend/main.py`**

```python
from fastapi import FastAPI
from api.auth import router as auth_router
from api.users import router as users_router
from api.servers import router as servers_router

app = FastAPI(title="ansible-inventory-ui", version="1.0.0")

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(servers_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Esegui tutta la suite**

```bash
cd ansible-inventory-ui/backend
pytest tests/ -v --tb=short
```

Expected: tutti i test passano (security + auth + users + servers)

- [ ] **Step 6: Commit**

```bash
cd ansible-inventory-ui
git add backend/api/servers.py backend/tests/test_servers.py backend/main.py
git commit -m "feat: server CRUD API — list, create, update, delete, duplicate check"
```

---

### Task 7: Deployment — Nginx + init.sh + Verifica finale

**Files:**
- Create: `ansible-inventory-ui/nginx/nginx.conf`
- Create: `ansible-inventory-ui/nginx/whitelist.conf`
- Create: `ansible-inventory-ui/init.sh`

Questi step si eseguono **sulla VPS** (non in locale).

- [ ] **Step 1: Crea `nginx/whitelist.conf`**

Inserisci i tuoi IP reali:
```nginx
allow 1.2.3.4;      # Sostituisci con il tuo IP statico
# allow 5.6.7.8;   # Secondo IP (scommenta per abilitare)
deny all;
```

- [ ] **Step 2: Crea `nginx/nginx.conf`**

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

        ssl_certificate     /etc/letsencrypt/live/tuodominio/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/tuodominio/privkey.pem;

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

- [ ] **Step 3: Crea `init.sh`**

```bash
#!/usr/bin/env bash
# Crea il primo utente Admin. Eseguire una sola volta dopo il primo deploy.
set -e

read -p "Username admin: " USERNAME
read -p "Email admin: " EMAIL
read -s -p "Password admin: " PASSWORD
echo

cd "$(dirname "$0")/backend"

docker compose -f ../docker-compose.yml exec backend python - <<EOF
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from config import settings
from database import Base
from models.user import User, UserRole
from core.security import hash_password
import models  # noqa

async def main():
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        user = User(
            username="$USERNAME",
            email="$EMAIL",
            hashed_password=hash_password("$PASSWORD"),
            role=UserRole.admin,
            is_active=True,
        )
        session.add(user)
        await session.commit()
    await engine.dispose()
    print("Utente Admin creato con successo.")

asyncio.run(main())
EOF
```

```bash
chmod +x init.sh
```

- [ ] **Step 4: Sulla VPS — installa nginx e certbot**

```bash
sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx
sudo systemctl enable nginx
```

- [ ] **Step 5: Sulla VPS — ottieni certificato SSL**

```bash
sudo certbot certonly --standalone -d tuodominio.example.com
```

Aggiorna i path in `nginx/nginx.conf` sostituendo `tuodominio` con il tuo dominio reale.

- [ ] **Step 6: Sulla VPS — deploy**

```bash
git clone <repo-url> ansible-inventory-ui
cd ansible-inventory-ui
cp .env.example .env
# Edita .env con JWT_SECRET reale e DATABASE_URL
docker compose up -d --build
cd backend && DATABASE_URL=postgresql+asyncpg://invui:invui@localhost:5432/invui alembic upgrade head
```

- [ ] **Step 7: Crea l'utente Admin iniziale**

```bash
./init.sh
```

- [ ] **Step 8: Copia nginx config e avvia**

```bash
sudo cp nginx/nginx.conf /etc/nginx/nginx.conf
sudo cp nginx/whitelist.conf /etc/nginx/whitelist.conf
sudo nginx -t && sudo systemctl reload nginx
```

- [ ] **Step 9: Verifica**

```bash
# Health check
curl https://tuodominio.example.com/health
# Expected: {"status":"ok"}

# Login con l'Admin appena creato
curl -X POST https://tuodominio.example.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"<admin>","password":"<pass>"}'
# Expected: {"access_token":"...","token_type":"bearer"}

# Swagger UI (solo da IP in whitelist)
# Apri: https://tuodominio.example.com/docs
```

- [ ] **Step 10: Commit finale**

```bash
cd ansible-inventory-ui
git add nginx/ init.sh
git commit -m "feat: nginx reverse proxy, SSL, init script"
```

---

## Self-Review — Copertura Spec (Piano 1)

| Requisito spec | Task |
|---|---|
| Docker Compose + PostgreSQL | Task 1, 7 |
| Modelli User, Server, AuditLog | Task 2 |
| JWT login (8h) | Task 3, 4 |
| TOTP (pyotp) — login a due step | Task 3, 4 |
| Codici di backup TOTP | Task 3, 4 |
| QR code setup TOTP (Admin) | Task 5 |
| Ruoli: Viewer / Editor / Admin | Task 4, 5, 6 |
| CRUD utenti (Admin) | Task 5 |
| CRUD server (Editor+) | Task 6 |
| Duplicate detection (hostname) | Task 6 |
| Filtri lista server | Task 6 |
| Nginx + SSL | Task 7 |
| init.sh primo utente Admin | Task 7 |

**Rinviato a Piano 2:**
- AWX client (lista inventory, aggiunta host, duplicate check via AWX)
- Airtable client (export, import, risoluzione conflitti)

**Rinviato a Piano 3:**
- Next.js frontend (wizard 4-step, login con TOTP, dashboard, admin UI)
