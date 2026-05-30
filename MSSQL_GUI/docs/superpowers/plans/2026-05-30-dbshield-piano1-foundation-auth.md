# DBShield Piano 1 — Foundation & Auth

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scaffoldare l'intera struttura del progetto DBShield con Docker Compose, database PostgreSQL, API FastAPI funzionante, autenticazione JWT completa con refresh token e 2FA TOTP opzionale/forzabile.

**Architecture:** Backend FastAPI con PostgreSQL via SQLAlchemy + Alembic, Redis per sessioni/cache, Celery per task asincroni. Frontend React (Vite + Tailwind + shadcn/ui) servito da Nginx. Ogni componente gira in container Docker separato orchestrato da Docker Compose.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, python-jose (JWT), bcrypt, pyotp (TOTP), cryptography (AES-256-GCM), PostgreSQL 15, Redis 7, Celery, React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, React Query, React Router v6, Nginx, Docker Compose.

---

## Struttura file creati in questo piano

```
MSSQL_GUI/
├── docker-compose.yml
├── docker-compose.dev.yml
├── .env.example
├── .gitignore
├── Makefile
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 0001_initial.py
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── organization.py
│   │   │   └── user.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   └── user.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── router.py
│   │   │       ├── auth.py
│   │   │       └── users.py
│   │   └── core/
│   │       ├── __init__.py
│   │       ├── security.py
│   │       └── encryption.py
│   └── tests/
│       ├── conftest.py
│       ├── test_auth.py
│       └── test_users.py
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── components.json
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── lib/
│       │   ├── api.ts
│       │   └── utils.ts
│       ├── hooks/
│       │   └── useAuth.ts
│       ├── stores/
│       │   └── authStore.ts
│       ├── components/
│       │   └── layout/
│       │       ├── AppLayout.tsx
│       │       ├── Sidebar.tsx
│       │       └── Header.tsx
│       └── pages/
│           ├── Login.tsx
│           ├── Setup2FA.tsx
│           └── Dashboard.tsx
└── nginx/
    └── nginx.conf
```

---

## Task 1: Struttura directory e file di configurazione base

**Files:**
- Create: `MSSQL_GUI/docker-compose.yml`
- Create: `MSSQL_GUI/docker-compose.dev.yml`
- Create: `MSSQL_GUI/.env.example`
- Create: `MSSQL_GUI/.gitignore`
- Create: `MSSQL_GUI/Makefile`
- Create: `MSSQL_GUI/nginx/nginx.conf`

- [ ] **Step 1: Crea la struttura directory**

```bash
cd D:/Claude_Code/MSSQL_GUI
mkdir -p backend/app/{models,schemas,api/v1,core}
mkdir -p backend/alembic/versions
mkdir -p backend/tests
mkdir -p frontend/src/{lib,hooks,stores,components/layout,pages}
mkdir -p nginx
touch backend/app/__init__.py
touch backend/app/models/__init__.py
touch backend/app/schemas/__init__.py
touch backend/app/api/__init__.py
touch backend/app/api/v1/__init__.py
touch backend/app/core/__init__.py
touch backend/tests/__init__.py
```

- [ ] **Step 2: Crea `.env.example`**

```env
# Database
POSTGRES_USER=dbshield
POSTGRES_PASSWORD=changeme_strong_password
POSTGRES_DB=dbshield
DATABASE_URL=postgresql+asyncpg://dbshield:changeme_strong_password@db:5432/dbshield

# Redis
REDIS_URL=redis://redis:6379/0

# Security
SECRET_KEY=changeme_generate_with_openssl_rand_hex_32
ENCRYPTION_KEY=changeme_generate_with_openssl_rand_hex_32
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30

# App
APP_NAME=DBShield
APP_ENV=production
CORS_ORIGINS=http://localhost,https://yourdomain.com

# Email (SMTP)
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=noreply@yourdomain.com
```

- [ ] **Step 3: Crea `docker-compose.yml`**

```yaml
version: "3.9"

services:
  db:
    image: postgres:15-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: unless-stopped
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000

  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: unless-stopped
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: celery -A app.celery_app worker --loglevel=info

  scheduler:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: unless-stopped
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: celery -A app.celery_app beat --loglevel=info

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - certbot_data:/etc/letsencrypt
    depends_on:
      - api
      - frontend

volumes:
  postgres_data:
  redis_data:
  certbot_data:
```

- [ ] **Step 4: Crea `docker-compose.dev.yml`**

```yaml
version: "3.9"

services:
  db:
    ports:
      - "5432:5432"

  redis:
    ports:
      - "6379:6379"

  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    volumes:
      - ./backend:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ports:
      - "8000:8000"

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    volumes:
      - ./frontend:/app
      - /app/node_modules
    command: npm run dev -- --host
    ports:
      - "5173:5173"
    environment:
      - VITE_API_URL=http://localhost:8000
```

- [ ] **Step 5: Crea `nginx/nginx.conf`**

```nginx
events {
    worker_connections 1024;
}

http {
    upstream api {
        server api:8000;
    }

    upstream frontend {
        server frontend:80;
    }

    server {
        listen 80;
        server_name _;

        # API
        location /api/ {
            proxy_pass http://api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        # Frontend
        location / {
            proxy_pass http://frontend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
}
```

- [ ] **Step 6: Crea `Makefile`**

```makefile
.PHONY: dev up down logs migrate test

dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f api

migrate:
	docker compose exec api alembic upgrade head

test:
	docker compose exec api pytest tests/ -v

shell:
	docker compose exec api bash
```

- [ ] **Step 7: Crea `.gitignore` nel progetto**

```gitignore
# Python
__pycache__/
*.py[cod]
.venv/
.env
*.egg-info/
dist/
.pytest_cache/
.coverage
htmlcov/

# Node
node_modules/
dist/
.env.local

# Docker
postgres_data/
redis_data/

# OS
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
```

- [ ] **Step 8: Commit**

```bash
cd D:/Claude_Code/MSSQL_GUI
git add .
git commit -m "feat: scaffold project structure and Docker Compose"
```

---

## Task 2: Backend — Dipendenze e configurazione FastAPI

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/requirements-dev.txt`
- Create: `backend/Dockerfile`
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`
- Create: `backend/app/main.py`

- [ ] **Step 1: Crea `backend/requirements.txt`**

```txt
fastapi==0.111.0
uvicorn[standard]==0.29.0
sqlalchemy[asyncio]==2.0.30
asyncpg==0.29.0
alembic==1.13.1
pydantic==2.7.1
pydantic-settings==2.2.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
pyotp==2.9.0
cryptography==42.0.7
celery[redis]==5.4.0
redis==5.0.4
httpx==0.27.0
python-multipart==0.0.9
emails==0.6.0
qrcode[pil]==7.4.2
```

- [ ] **Step 2: Crea `backend/requirements-dev.txt`**

```txt
-r requirements.txt
pytest==8.2.0
pytest-asyncio==0.23.6
pytest-cov==5.0.0
httpx==0.27.0
anyio==4.3.0
```

- [ ] **Step 3: Crea `backend/Dockerfile`**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/app
```

- [ ] **Step 4: Crea `backend/app/config.py`**

```python
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "DBShield"
    app_env: str = "production"

    # Database
    database_url: str

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Security
    secret_key: str
    encryption_key: str
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # CORS
    cors_origins: str = "http://localhost"

    # SMTP
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@dbshield.io"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 5: Crea `backend/app/database.py`**

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.app_env == "development",
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

- [ ] **Step 6: Crea `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.api.v1.router import router as v1_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    docs_url="/api/docs" if settings.app_env != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router, prefix="/api/v1")


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.app_name}
```

- [ ] **Step 7: Crea `backend/app/api/v1/router.py`**

```python
from fastapi import APIRouter
from app.api.v1 import auth, users

router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(users.router, prefix="/users", tags=["users"])
```

- [ ] **Step 8: Crea `backend/app/api/v1/auth.py` (placeholder vuoto)**

```python
from fastapi import APIRouter

router = APIRouter()
```

- [ ] **Step 9: Crea `backend/app/api/v1/users.py` (placeholder vuoto)**

```python
from fastapi import APIRouter

router = APIRouter()
```

- [ ] **Step 10: Verifica che FastAPI si avvii**

```bash
cd D:/Claude_Code/MSSQL_GUI
cp .env.example .env
# Modifica .env con valori validi (SECRET_KEY e ENCRYPTION_KEY devono essere 32 hex chars)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up db redis api
# Apri http://localhost:8000/api/health — deve rispondere {"status":"ok","app":"DBShield"}
```

- [ ] **Step 11: Commit**

```bash
git add backend/
git commit -m "feat: add FastAPI app skeleton with config and database"
```

---

## Task 3: Modelli database — Organization e User

**Files:**
- Create: `backend/app/models/base.py`
- Create: `backend/app/models/organization.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0001_initial.py`

- [ ] **Step 1: Crea `backend/app/models/base.py`**

```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
```

- [ ] **Step 2: Crea `backend/app/models/organization.py`**

```python
import uuid
from sqlalchemy import String, Boolean, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin
import enum


class OrgPlan(str, enum.Enum):
    saas_starter = "saas_starter"
    saas_business = "saas_business"
    saas_enterprise = "saas_enterprise"
    onpremise = "onpremise"


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[OrgPlan] = mapped_column(
        SAEnum(OrgPlan), nullable=False, default=OrgPlan.saas_starter
    )
    license_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    require_2fa: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    users: Mapped[list["User"]] = relationship("User", back_populates="organization")
```

- [ ] **Step 3: Crea `backend/app/models/user.py`**

```python
import uuid
from sqlalchemy import String, Boolean, ForeignKey, Enum as SAEnum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin
import enum


class UserRole(str, enum.Enum):
    superadmin = "superadmin"
    admin = "admin"
    operator = "operator"
    viewer = "viewer"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole), nullable=False, default=UserRole.viewer
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # 2FA
    two_fa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    two_fa_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    two_fa_backup_codes_enc: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="users")
```

- [ ] **Step 4: Aggiorna `backend/app/models/__init__.py`**

```python
from app.models.base import Base
from app.models.organization import Organization, OrgPlan
from app.models.user import User, UserRole

__all__ = ["Base", "Organization", "OrgPlan", "User", "UserRole"]
```

- [ ] **Step 5: Crea `backend/alembic.ini`**

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
version_path_separator = os
sqlalchemy.url = driver://user:pass@localhost/dbname

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 6: Crea `backend/alembic/env.py`**

```python
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from app.config import get_settings
from app.models import Base

config = context.config
settings = get_settings()

config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
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

- [ ] **Step 7: Crea `backend/alembic/versions/0001_initial.py`**

```python
"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "plan",
            sa.Enum("saas_starter", "saas_business", "saas_enterprise", "onpremise", name="orgplan"),
            nullable=False,
            server_default="saas_starter",
        ),
        sa.Column("license_key", sa.String(255), nullable=True),
        sa.Column("require_2fa", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("superadmin", "admin", "operator", "viewer", name="userrole"),
            nullable=False,
            server_default="viewer",
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("two_fa_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("two_fa_secret_enc", sa.Text, nullable=True),
        sa.Column("two_fa_backup_codes_enc", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index("ix_users_email", "users", ["email"])


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_table("organizations")
    op.execute("DROP TYPE IF EXISTS userrole")
    op.execute("DROP TYPE IF EXISTS orgplan")
```

- [ ] **Step 8: Applica la migrazione**

```bash
docker compose exec api alembic upgrade head
# Expected output: Running upgrade -> 0001, initial schema
```

- [ ] **Step 9: Commit**

```bash
git add backend/
git commit -m "feat: add Organization and User models with Alembic migration"
```

---

## Task 4: Core security — JWT, bcrypt, AES-256

**Files:**
- Create: `backend/app/core/security.py`
- Create: `backend/app/core/encryption.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_security.py`

- [ ] **Step 1: Scrivi i test (failing)**

Crea `backend/tests/test_security.py`:

```python
import pytest
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.encryption import encrypt, decrypt


def test_hash_password_returns_bcrypt_hash():
    hashed = hash_password("mypassword")
    assert hashed.startswith("$2b$")
    assert hashed != "mypassword"


def test_verify_password_correct():
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("mypassword")
    assert verify_password("wrongpassword", hashed) is False


def test_create_and_decode_access_token():
    token = create_access_token(subject="user-id-123", role="admin")
    payload = decode_token(token)
    assert payload["sub"] == "user-id-123"
    assert payload["role"] == "admin"
    assert payload["type"] == "access"


def test_create_and_decode_refresh_token():
    token = create_refresh_token(subject="user-id-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-id-123"
    assert payload["type"] == "refresh"


def test_decode_invalid_token_returns_none():
    result = decode_token("invalid.token.here")
    assert result is None


def test_encrypt_decrypt_roundtrip():
    plaintext = "sensitive_data_here"
    encrypted = encrypt(plaintext)
    assert encrypted != plaintext
    assert decrypt(encrypted) == plaintext


def test_encrypt_same_value_different_ciphertext():
    encrypted1 = encrypt("same_value")
    encrypted2 = encrypt("same_value")
    # AES-GCM usa nonce random, deve produrre ciphertext diversi
    assert encrypted1 != encrypted2
```

- [ ] **Step 2: Esegui i test — verifica che falliscano**

```bash
docker compose exec api pytest tests/test_security.py -v
# Expected: ImportError o ModuleNotFoundError — i moduli non esistono ancora
```

- [ ] **Step 3: Implementa `backend/app/core/security.py`**

```python
from datetime import datetime, timedelta, timezone
from typing import Any
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {
        "sub": subject,
        "role": role,
        "type": "access",
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def create_refresh_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.refresh_token_expire_days
    )
    payload = {
        "sub": subject,
        "type": "refresh",
        "exp": expire,
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
    except JWTError:
        return None
```

- [ ] **Step 4: Implementa `backend/app/core/encryption.py`**

```python
import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import get_settings

settings = get_settings()


def _get_key() -> bytes:
    key_hex = settings.encryption_key
    # Assicura 32 bytes (256 bit)
    key_bytes = bytes.fromhex(key_hex[:64].ljust(64, "0"))
    return key_bytes


def encrypt(plaintext: str) -> str:
    """Cifra una stringa con AES-256-GCM. Ritorna base64(nonce + ciphertext)."""
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    combined = nonce + ciphertext
    return base64.b64encode(combined).decode()


def decrypt(encrypted: str) -> str:
    """Decifra una stringa cifrata con encrypt()."""
    key = _get_key()
    aesgcm = AESGCM(key)
    combined = base64.b64decode(encrypted.encode())
    nonce = combined[:12]
    ciphertext = combined[12:]
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode()
```

- [ ] **Step 5: Crea `backend/tests/conftest.py`**

```python
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.main import app
from app.database import get_db
from app.models import Base

TEST_DATABASE_URL = "postgresql+asyncpg://dbshield:changeme_strong_password@db:5432/dbshield_test"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session():
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
```

- [ ] **Step 6: Esegui i test — verifica che passino**

```bash
docker compose exec api pytest tests/test_security.py -v
# Expected: 9 passed
```

- [ ] **Step 7: Commit**

```bash
git add backend/
git commit -m "feat: add JWT security and AES-256-GCM encryption core"
```

---

## Task 5: Autenticazione — Login, Logout, Refresh token

**Files:**
- Create/Modify: `backend/app/schemas/auth.py`
- Create/Modify: `backend/app/schemas/user.py`
- Modify: `backend/app/api/v1/auth.py`
- Create: `backend/app/api/deps.py`
- Create: `backend/tests/test_auth.py`

- [ ] **Step 1: Crea `backend/app/schemas/auth.py`**

```python
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    totp_code: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class Require2FAResponse(BaseModel):
    require_2fa: bool = True
    message: str = "2FA code required"
```

- [ ] **Step 2: Crea `backend/app/schemas/user.py`**

```python
import uuid
from pydantic import BaseModel, EmailStr
from app.models.user import UserRole


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    role: UserRole
    two_fa_enabled: bool
    is_active: bool

    model_config = {"from_attributes": True}


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: UserRole = UserRole.viewer
```

- [ ] **Step 3: Crea `backend/app/api/deps.py`**

```python
from fastapi import Depends, HTTPException, Cookie, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.core.security import decode_token
from app.models.user import User


async def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )
    if not access_token:
        raise credentials_exception

    payload = decode_token(access_token)
    if payload is None or payload.get("type") != "access":
        raise credentials_exception

    user_id: str = payload.get("sub")
    if not user_id:
        raise credentials_exception

    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user


def require_role(*roles: str):
    async def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return current_user
    return checker
```

- [ ] **Step 4: Scrivi i test di autenticazione (failing)**

Crea `backend/tests/test_auth.py`:

```python
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.organization import Organization, OrgPlan
from app.models.user import User, UserRole
from app.core.security import hash_password


@pytest.fixture
async def org_and_user(db_session: AsyncSession):
    org = Organization(name="Test Org", plan=OrgPlan.saas_starter)
    db_session.add(org)
    await db_session.flush()

    user = User(
        org_id=org.id,
        email="test@example.com",
        password_hash=hash_password("password123"),
        role=UserRole.admin,
    )
    db_session.add(user)
    await db_session.commit()
    return org, user


async def test_login_success(client: AsyncClient, org_and_user):
    response = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "password123",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert response.cookies.get("access_token") is not None
    assert response.cookies.get("refresh_token") is not None


async def test_login_wrong_password(client: AsyncClient, org_and_user):
    response = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "wrongpassword",
    })
    assert response.status_code == 401


async def test_login_nonexistent_user(client: AsyncClient):
    response = await client.post("/api/v1/auth/login", json={
        "email": "ghost@example.com",
        "password": "any",
    })
    assert response.status_code == 401


async def test_me_authenticated(client: AsyncClient, org_and_user):
    # Prima fai login
    login = await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "password123",
    })
    assert login.status_code == 200

    # Poi chiama /me
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"


async def test_me_unauthenticated(client: AsyncClient):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_logout(client: AsyncClient, org_and_user):
    await client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "password123",
    })
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    # Cookie deve essere cancellato
    assert response.cookies.get("access_token") == "" or "access_token" not in response.cookies
```

- [ ] **Step 5: Esegui i test — verifica che falliscano**

```bash
docker compose exec api pytest tests/test_auth.py -v
# Expected: 404 o errori — gli endpoint non esistono ancora
```

- [ ] **Step 6: Implementa `backend/app/api/v1/auth.py`**

```python
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Response, Cookie, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
)
from app.schemas.auth import LoginRequest, TokenResponse, Require2FAResponse
from app.schemas.user import UserOut
from app.api.deps import get_current_user
from app.config import get_settings
import pyotp

router = APIRouter()
settings = get_settings()

COOKIE_OPTS = dict(httponly=True, samesite="lax", secure=settings.app_env == "production")


@router.post("/login")
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.email == payload.email, User.is_active == True)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # 2FA check
    if user.two_fa_enabled:
        if not payload.totp_code:
            return Require2FAResponse()
        from app.core.encryption import decrypt
        secret = decrypt(user.two_fa_secret_enc)
        totp = pyotp.TOTP(secret)
        if not totp.verify(payload.totp_code, valid_window=1):
            raise HTTPException(status_code=401, detail="Invalid 2FA code")

    access_token = create_access_token(subject=str(user.id), role=user.role)
    refresh_token = create_refresh_token(subject=str(user.id))

    response.set_cookie("access_token", access_token, max_age=settings.access_token_expire_minutes * 60, **COOKIE_OPTS)
    response.set_cookie("refresh_token", refresh_token, max_age=settings.refresh_token_expire_days * 86400, **COOKIE_OPTS)

    return TokenResponse(access_token=access_token)


@router.post("/refresh")
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    payload = decode_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    result = await db.execute(select(User).where(User.id == payload["sub"], User.is_active == True))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    access_token = create_access_token(subject=str(user.id), role=user.role)
    response.set_cookie("access_token", access_token, max_age=settings.access_token_expire_minutes * 60, **COOKIE_OPTS)

    return TokenResponse(access_token=access_token)


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Logged out"}


@router.get("/me", response_model=UserOut)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
```

- [ ] **Step 7: Esegui i test — verifica che passino**

```bash
docker compose exec api pytest tests/test_auth.py -v
# Expected: 5 passed
```

- [ ] **Step 8: Commit**

```bash
git add backend/
git commit -m "feat: implement JWT auth with login, logout, refresh endpoints"
```

---

## Task 6: 2FA — Setup TOTP e verifica

**Files:**
- Modify: `backend/app/api/v1/auth.py`
- Create: `backend/tests/test_2fa.py`

- [ ] **Step 1: Scrivi i test 2FA (failing)**

Crea `backend/tests/test_2fa.py`:

```python
import pytest
import pyotp
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.organization import Organization, OrgPlan
from app.models.user import User, UserRole
from app.core.security import hash_password
from app.core.encryption import decrypt


@pytest.fixture
async def authenticated_client(client: AsyncClient, db_session: AsyncSession):
    org = Organization(name="2FA Org", plan=OrgPlan.saas_starter)
    db_session.add(org)
    await db_session.flush()
    user = User(
        org_id=org.id,
        email="twofa@example.com",
        password_hash=hash_password("pass123"),
        role=UserRole.admin,
    )
    db_session.add(user)
    await db_session.commit()

    await client.post("/api/v1/auth/login", json={"email": "twofa@example.com", "password": "pass123"})
    return client, user


async def test_setup_2fa_returns_qr_and_secret(authenticated_client):
    client, _ = authenticated_client
    response = await client.post("/api/v1/auth/2fa/setup")
    assert response.status_code == 200
    data = response.json()
    assert "secret" in data
    assert "qr_code" in data  # base64 PNG


async def test_verify_2fa_enables_it(authenticated_client, db_session: AsyncSession):
    client, user = authenticated_client
    # Setup
    setup = await client.post("/api/v1/auth/2fa/setup")
    secret = setup.json()["secret"]
    # Verifica con codice valido
    totp = pyotp.TOTP(secret)
    code = totp.now()
    response = await client.post("/api/v1/auth/2fa/verify", json={"code": code, "secret": secret})
    assert response.status_code == 200
    data = response.json()
    assert data["enabled"] is True
    assert "backup_codes" in data
    assert len(data["backup_codes"]) == 8


async def test_verify_2fa_wrong_code_fails(authenticated_client):
    client, _ = authenticated_client
    await client.post("/api/v1/auth/2fa/setup")
    response = await client.post("/api/v1/auth/2fa/verify", json={"code": "000000", "secret": pyotp.random_base32()})
    assert response.status_code == 400


async def test_disable_2fa(authenticated_client, db_session: AsyncSession):
    client, user = authenticated_client
    # Abilita prima
    setup = await client.post("/api/v1/auth/2fa/setup")
    secret = setup.json()["secret"]
    totp = pyotp.TOTP(secret)
    await client.post("/api/v1/auth/2fa/verify", json={"code": totp.now(), "secret": secret})
    # Disabilita
    response = await client.post("/api/v1/auth/2fa/disable", json={"password": "pass123"})
    assert response.status_code == 200
    assert response.json()["enabled"] is False
```

- [ ] **Step 2: Esegui i test — verifica che falliscano**

```bash
docker compose exec api pytest tests/test_2fa.py -v
# Expected: 404 — gli endpoint non esistono
```

- [ ] **Step 3: Aggiungi gli endpoint 2FA in `backend/app/api/v1/auth.py`**

Aggiungi in fondo al file esistente:

```python
import pyotp
import qrcode
import qrcode.image.svg
import io
import base64
import secrets
from app.core.encryption import encrypt, decrypt
from pydantic import BaseModel


class TwoFAVerifyRequest(BaseModel):
    code: str
    secret: str


class TwoFADisableRequest(BaseModel):
    password: str


@router.post("/2fa/setup")
async def setup_2fa(current_user: User = Depends(get_current_user)):
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=current_user.email, issuer_name=settings.app_name)

    # Genera QR code PNG in base64
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return {"secret": secret, "qr_code": qr_b64}


@router.post("/2fa/verify")
async def verify_2fa(
    payload: TwoFAVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    totp = pyotp.TOTP(payload.secret)
    if not totp.verify(payload.code, valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid 2FA code")

    # Genera 8 backup codes
    backup_codes = [secrets.token_hex(4).upper() for _ in range(8)]

    current_user.two_fa_enabled = True
    current_user.two_fa_secret_enc = encrypt(payload.secret)
    current_user.two_fa_backup_codes_enc = encrypt(",".join(backup_codes))
    db.add(current_user)
    await db.commit()

    return {"enabled": True, "backup_codes": backup_codes}


@router.post("/2fa/disable")
async def disable_2fa(
    payload: TwoFADisableRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong password")

    current_user.two_fa_enabled = False
    current_user.two_fa_secret_enc = None
    current_user.two_fa_backup_codes_enc = None
    db.add(current_user)
    await db.commit()

    return {"enabled": False}
```

- [ ] **Step 4: Esegui i test — verifica che passino**

```bash
docker compose exec api pytest tests/test_2fa.py -v
# Expected: 4 passed
```

- [ ] **Step 5: Commit**

```bash
git add backend/
git commit -m "feat: implement TOTP 2FA setup, verify, and disable endpoints"
```

---

## Task 7: Frontend — Scaffold React + Vite + Tailwind + shadcn/ui

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/components.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/Dockerfile`

- [ ] **Step 1: Crea `frontend/package.json`**

```json
{
  "name": "dbshield-frontend",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "@radix-ui/react-avatar": "^1.0.4",
    "@radix-ui/react-dialog": "^1.0.5",
    "@radix-ui/react-dropdown-menu": "^2.0.6",
    "@radix-ui/react-label": "^2.0.2",
    "@radix-ui/react-slot": "^1.0.2",
    "@radix-ui/react-toast": "^1.1.5",
    "@radix-ui/react-tooltip": "^1.0.7",
    "@tanstack/react-query": "^5.40.0",
    "axios": "^1.7.2",
    "class-variance-authority": "^0.7.0",
    "clsx": "^2.1.1",
    "lucide-react": "^0.383.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-hook-form": "^7.51.5",
    "react-router-dom": "^6.23.1",
    "tailwind-merge": "^2.3.0",
    "tailwindcss-animate": "^1.0.7",
    "zod": "^3.23.8",
    "@hookform/resolvers": "^3.6.0"
  },
  "devDependencies": {
    "@types/node": "^20.14.2",
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "autoprefixer": "^10.4.19",
    "postcss": "^8.4.38",
    "tailwindcss": "^3.4.4",
    "typescript": "^5.4.5",
    "vite": "^5.3.1"
  }
}
```

- [ ] **Step 2: Crea `frontend/vite.config.ts`**

```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/api": {
        target: process.env.VITE_API_URL || "http://api:8000",
        changeOrigin: true,
      },
    },
  },
});
```

- [ ] **Step 3: Crea `frontend/tsconfig.json`**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "baseUrl": ".",
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 4: Crea `frontend/tsconfig.node.json`**

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 5: Crea `frontend/tailwind.config.ts`**

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
```

- [ ] **Step 6: Crea `frontend/components.json`** (configurazione shadcn/ui)

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "default",
  "rsc": false,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "src/index.css",
    "baseColor": "slate",
    "cssVariables": true
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils"
  }
}
```

- [ ] **Step 7: Crea `frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="it">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>DBShield — MSSQL Backup Manager</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 8: Crea `frontend/src/index.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 222.2 84% 4.9%;
    --card: 0 0% 100%;
    --card-foreground: 222.2 84% 4.9%;
    --primary: 221.2 83.2% 53.3%;
    --primary-foreground: 210 40% 98%;
    --secondary: 210 40% 96.1%;
    --secondary-foreground: 222.2 47.4% 11.2%;
    --muted: 210 40% 96.1%;
    --muted-foreground: 215.4 16.3% 46.9%;
    --accent: 210 40% 96.1%;
    --accent-foreground: 222.2 47.4% 11.2%;
    --destructive: 0 84.2% 60.2%;
    --destructive-foreground: 210 40% 98%;
    --border: 214.3 31.8% 91.4%;
    --input: 214.3 31.8% 91.4%;
    --ring: 221.2 83.2% 53.3%;
    --radius: 0.5rem;
  }

  .dark {
    --background: 222.2 84% 4.9%;
    --foreground: 210 40% 98%;
    --card: 222.2 84% 4.9%;
    --card-foreground: 210 40% 98%;
    --primary: 217.2 91.2% 59.8%;
    --primary-foreground: 222.2 47.4% 11.2%;
    --secondary: 217.2 32.6% 17.5%;
    --secondary-foreground: 210 40% 98%;
    --muted: 217.2 32.6% 17.5%;
    --muted-foreground: 215 20.2% 65.1%;
    --accent: 217.2 32.6% 17.5%;
    --accent-foreground: 210 40% 98%;
    --destructive: 0 62.8% 30.6%;
    --destructive-foreground: 210 40% 98%;
    --border: 217.2 32.6% 17.5%;
    --input: 217.2 32.6% 17.5%;
    --ring: 224.3 76.3% 48%;
  }
}

@layer base {
  * {
    @apply border-border;
  }
  body {
    @apply bg-background text-foreground;
  }
}
```

- [ ] **Step 9: Crea `frontend/src/lib/utils.ts`**

```typescript
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

- [ ] **Step 10: Crea `frontend/src/lib/api.ts`**

```typescript
import axios from "axios";

const api = axios.create({
  baseURL: "/api/v1",
  withCredentials: true, // invia cookie httpOnly
});

// Interceptor: se 401 tenta refresh, poi riprova
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        await axios.post("/api/v1/auth/refresh", {}, { withCredentials: true });
        return api(originalRequest);
      } catch {
        window.location.href = "/login";
      }
    }
    return Promise.reject(error);
  }
);

export default api;
```

- [ ] **Step 11: Crea `frontend/src/stores/authStore.ts`**

```typescript
import { create } from "zustand";

interface User {
  id: string;
  email: string;
  role: string;
  two_fa_enabled: boolean;
}

interface AuthState {
  user: User | null;
  setUser: (user: User | null) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  setUser: (user) => set({ user }),
}));
```

- [ ] **Step 12: Crea `frontend/src/hooks/useAuth.ts`**

```typescript
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/stores/authStore";
import api from "@/lib/api";
import { useEffect } from "react";

export function useAuth() {
  const { user, setUser } = useAuthStore();

  const { data, isLoading, error } = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const res = await api.get("/auth/me");
      return res.data;
    },
    retry: false,
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (data) setUser(data);
    if (error) setUser(null);
  }, [data, error, setUser]);

  return { user: data ?? user, isLoading, isAuthenticated: !!data };
}
```

- [ ] **Step 13: Crea `frontend/src/main.tsx`**

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { refetchOnWindowFocus: false },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </React.StrictMode>
);
```

- [ ] **Step 14: Crea `frontend/src/App.tsx`**

```tsx
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import Login from "@/pages/Login";
import Dashboard from "@/pages/Dashboard";
import AppLayout from "@/components/layout/AppLayout";

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return <div className="flex h-screen items-center justify-center">Caricamento...</div>;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <AppLayout />
            </ProtectedRoute>
          }
        >
          <Route index element={<Dashboard />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 15: Crea `frontend/Dockerfile`**

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx-spa.conf /etc/nginx/conf.d/default.conf
```

- [ ] **Step 16: Crea `frontend/nginx-spa.conf`** (serve SPA correttamente)

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 17: Commit**

```bash
git add frontend/
git commit -m "feat: scaffold React frontend with Vite, Tailwind, shadcn/ui"
```

---

## Task 8: Frontend — Pagina Login

**Files:**
- Create: `frontend/src/pages/Login.tsx`
- Create: `frontend/src/components/ui/button.tsx`
- Create: `frontend/src/components/ui/input.tsx`
- Create: `frontend/src/components/ui/label.tsx`
- Create: `frontend/src/components/ui/card.tsx`

- [ ] **Step 1: Installa componenti shadcn/ui base**

```bash
cd frontend
# Esegui dentro il container o localmente se hai node
docker compose exec frontend sh -c "npx shadcn-ui@latest add button input label card"
```

Se non disponibile nel container, crea manualmente i componenti:

- [ ] **Step 2: Crea `frontend/src/components/ui/button.tsx`**

```tsx
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline: "border border-input bg-background hover:bg-accent hover:text-accent-foreground",
        ghost: "hover:bg-accent hover:text-accent-foreground",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-9 rounded-md px-3",
        lg: "h-11 rounded-md px-8",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return <Comp className={cn(buttonVariants({ variant, size, className }))} ref={ref} {...props} />;
  }
);
Button.displayName = "Button";

export { Button, buttonVariants };
```

- [ ] **Step 3: Crea `frontend/src/components/ui/input.tsx`**

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => (
    <input
      type={type}
      className={cn(
        "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      ref={ref}
      {...props}
    />
  )
);
Input.displayName = "Input";

export { Input };
```

- [ ] **Step 4: Crea `frontend/src/components/ui/label.tsx`**

```tsx
import * as React from "react";
import * as LabelPrimitive from "@radix-ui/react-label";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const labelVariants = cva(
  "text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
);

const Label = React.forwardRef<
  React.ElementRef<typeof LabelPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root> & VariantProps<typeof labelVariants>
>(({ className, ...props }, ref) => (
  <LabelPrimitive.Root ref={ref} className={cn(labelVariants(), className)} {...props} />
));
Label.displayName = LabelPrimitive.Root.displayName;

export { Label };
```

- [ ] **Step 5: Crea `frontend/src/components/ui/card.tsx`**

```tsx
import * as React from "react";
import { cn } from "@/lib/utils";

const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("rounded-lg border bg-card text-card-foreground shadow-sm", className)} {...props} />
  )
);
Card.displayName = "Card";

const CardHeader = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("flex flex-col space-y-1.5 p-6", className)} {...props} />
  )
);
CardHeader.displayName = "CardHeader";

const CardTitle = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3 ref={ref} className={cn("text-2xl font-semibold leading-none tracking-tight", className)} {...props} />
  )
);
CardTitle.displayName = "CardTitle";

const CardDescription = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p ref={ref} className={cn("text-sm text-muted-foreground", className)} {...props} />
  )
);
CardDescription.displayName = "CardDescription";

const CardContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("p-6 pt-0", className)} {...props} />
  )
);
CardContent.displayName = "CardContent";

export { Card, CardHeader, CardTitle, CardDescription, CardContent };
```

- [ ] **Step 6: Crea `frontend/src/pages/Login.tsx`**

```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import api from "@/lib/api";

const loginSchema = z.object({
  email: z.string().email("Email non valida"),
  password: z.string().min(1, "Password obbligatoria"),
  totp_code: z.string().optional(),
});

type LoginForm = z.infer<typeof loginSchema>;

export default function Login() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [requires2FA, setRequires2FA] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const { register, handleSubmit, formState: { errors } } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  const mutation = useMutation({
    mutationFn: (data: LoginForm) => api.post("/auth/login", data),
    onSuccess: (res) => {
      if (res.data?.require_2fa) {
        setRequires2FA(true);
        return;
      }
      queryClient.invalidateQueries({ queryKey: ["me"] });
      navigate("/");
    },
    onError: (err: any) => {
      setErrorMsg(err.response?.data?.detail || "Credenziali non valide");
    },
  });

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 to-slate-800 p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="bg-primary rounded-xl p-2">
            <ShieldCheck className="h-8 w-8 text-white" />
          </div>
          <span className="text-3xl font-bold text-white">DBShield</span>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Accedi</CardTitle>
            <CardDescription>Inserisci le tue credenziali per continuare</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit((data) => mutation.mutate(data))} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="nome@azienda.com"
                  {...register("email")}
                />
                {errors.email && <p className="text-destructive text-xs">{errors.email.message}</p>}
              </div>

              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  {...register("password")}
                />
                {errors.password && <p className="text-destructive text-xs">{errors.password.message}</p>}
              </div>

              {requires2FA && (
                <div className="space-y-2">
                  <Label htmlFor="totp_code">Codice Autenticatore (6 cifre)</Label>
                  <Input
                    id="totp_code"
                    type="text"
                    inputMode="numeric"
                    maxLength={6}
                    placeholder="000000"
                    {...register("totp_code")}
                    autoFocus
                  />
                </div>
              )}

              {errorMsg && (
                <div className="bg-destructive/10 text-destructive text-sm rounded-md px-3 py-2">
                  {errorMsg}
                </div>
              )}

              <Button type="submit" className="w-full" disabled={mutation.isPending}>
                {mutation.isPending ? (
                  <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Accesso in corso...</>
                ) : (
                  requires2FA ? "Verifica codice" : "Accedi"
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        <p className="text-center text-slate-400 text-sm mt-4">
          DBShield v1.0 — MSSQL Backup Manager
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 7: Commit**

```bash
git add frontend/
git commit -m "feat: add Login page with 2FA support"
```

---

## Task 9: Frontend — Layout principale e Dashboard base

**Files:**
- Create: `frontend/src/components/layout/AppLayout.tsx`
- Create: `frontend/src/components/layout/Sidebar.tsx`
- Create: `frontend/src/components/layout/Header.tsx`
- Create: `frontend/src/pages/Dashboard.tsx`

- [ ] **Step 1: Crea `frontend/src/components/layout/Sidebar.tsx`**

```tsx
import { Link, useLocation } from "react-router-dom";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Server,
  Database,
  HardDrive,
  FileText,
  Users,
  Settings,
  ShieldCheck,
} from "lucide-react";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/servers", icon: Server, label: "Server" },
  { to: "/jobs", icon: Database, label: "Backup Jobs" },
  { to: "/storage", icon: HardDrive, label: "Storage" },
  { to: "/logs", icon: FileText, label: "Log" },
  { to: "/users", icon: Users, label: "Utenti" },
  { to: "/settings", icon: Settings, label: "Impostazioni" },
];

export default function Sidebar() {
  const { pathname } = useLocation();

  return (
    <aside className="w-64 min-h-screen bg-slate-900 text-slate-100 flex flex-col">
      {/* Logo */}
      <div className="flex items-center gap-2 p-6 border-b border-slate-700">
        <div className="bg-primary rounded-lg p-1.5">
          <ShieldCheck className="h-5 w-5 text-white" />
        </div>
        <span className="font-bold text-lg">DBShield</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map(({ to, icon: Icon, label }) => (
          <Link
            key={to}
            to={to}
            className={cn(
              "flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors",
              pathname === to
                ? "bg-primary text-white"
                : "text-slate-400 hover:text-slate-100 hover:bg-slate-800"
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-slate-700 text-xs text-slate-500">
        v1.0.0
      </div>
    </aside>
  );
}
```

- [ ] **Step 2: Crea `frontend/src/components/layout/Header.tsx`**

```tsx
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { LogOut, User } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/hooks/useAuth";
import api from "@/lib/api";

export default function Header() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const logout = useMutation({
    mutationFn: () => api.post("/auth/logout"),
    onSuccess: () => {
      queryClient.clear();
      navigate("/login");
    },
  });

  return (
    <header className="h-14 border-b bg-background flex items-center justify-between px-6">
      <div />
      <div className="flex items-center gap-4">
        {user && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <User className="h-4 w-4" />
            <span>{user.email}</span>
            <span className="bg-muted px-2 py-0.5 rounded text-xs capitalize">{user.role}</span>
          </div>
        )}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => logout.mutate()}
          title="Logout"
        >
          <LogOut className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
}
```

- [ ] **Step 3: Crea `frontend/src/components/layout/AppLayout.tsx`**

```tsx
import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import Header from "./Header";

export default function AppLayout() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <Header />
        <main className="flex-1 p-6 bg-muted/20">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Crea `frontend/src/pages/Dashboard.tsx`**

```tsx
import { ShieldCheck, Server, Database, AlertTriangle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const stats = [
  { label: "Server Online", value: "—", icon: Server, color: "text-green-500" },
  { label: "Job Attivi", value: "—", icon: Database, color: "text-blue-500" },
  { label: "Backup Oggi", value: "—", icon: ShieldCheck, color: "text-primary" },
  { label: "Errori", value: "—", icon: AlertTriangle, color: "text-destructive" },
];

export default function Dashboard() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">Panoramica del sistema di backup</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map(({ label, value, icon: Icon, color }) => (
          <Card key={label}>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
              <Icon className={cn("h-5 w-5", color)} />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Attività recente</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground text-sm">
            Nessun backup eseguito ancora. Aggiungi un server e configura un job per iniziare.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

function cn(...classes: string[]) {
  return classes.filter(Boolean).join(" ");
}
```

- [ ] **Step 5: Verifica che il frontend si avvii**

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up frontend
# Apri http://localhost:5173 — deve mostrare la pagina di Login
# Prova ad accedere — deve reindirizzare alla Dashboard con sidebar
```

- [ ] **Step 6: Commit**

```bash
git add frontend/
git commit -m "feat: add app layout with sidebar, header, and dashboard skeleton"
```

---

## Task 10: Test end-to-end del Piano 1

- [ ] **Step 1: Avvia l'intero stack**

```bash
cd D:/Claude_Code/MSSQL_GUI
cp .env.example .env
# Modifica .env: genera SECRET_KEY e ENCRYPTION_KEY con:
# python -c "import secrets; print(secrets.token_hex(32))"
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

- [ ] **Step 2: Applica migrazioni**

```bash
docker compose exec api alembic upgrade head
```

- [ ] **Step 3: Crea utente superadmin iniziale**

```bash
docker compose exec api python -c "
import asyncio
from app.database import AsyncSessionLocal
from app.models.organization import Organization, OrgPlan
from app.models.user import User, UserRole
from app.core.security import hash_password

async def create_admin():
    async with AsyncSessionLocal() as db:
        org = Organization(name='EDM Informatica', plan=OrgPlan.saas_enterprise)
        db.add(org)
        await db.flush()
        user = User(
            org_id=org.id,
            email='admin@edminformatica.com',
            password_hash=hash_password('Admin123!'),
            role=UserRole.superadmin,
        )
        db.add(user)
        await db.commit()
        print(f'Creato: {user.email} / Admin123!')

asyncio.run(create_admin())
"
```

- [ ] **Step 4: Esegui tutti i test backend**

```bash
docker compose exec api pytest tests/ -v --cov=app --cov-report=term-missing
# Expected: tutti i test passano, copertura > 80%
```

- [ ] **Step 5: Verifica manuale flusso completo**

1. Apri `http://localhost:5173`
2. Login con `admin@edminformatica.com` / `Admin123!`
3. Verifica redirect alla Dashboard
4. Verifica sidebar con tutte le voci
5. Verifica logout funzionante

- [ ] **Step 6: Tag versione**

```bash
git tag v0.1.0-foundation
git commit --allow-empty -m "chore: Piano 1 Foundation & Auth completato"
```

---

## Riepilogo Piano 1

Al termine di questo piano avrai:
- ✅ Stack Docker Compose completo e funzionante
- ✅ Database PostgreSQL con schema Organization + User
- ✅ API FastAPI con autenticazione JWT (access + refresh token httpOnly)
- ✅ 2FA TOTP completo (setup, verifica, disabilita, backup codes)
- ✅ Cifratura AES-256-GCM per dati sensibili
- ✅ Test suite backend con copertura > 80%
- ✅ Frontend React con Login, Layout, Dashboard skeleton
- ✅ Dark/light mode CSS variables pronte

**Prossimo passo:** Piano 2 — Core Backend (server, database, storage destinations, backup jobs API)
