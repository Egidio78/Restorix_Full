# DBShield / Restorix — MSSQL Backup Manager

Piattaforma SaaS / on-premise per il backup automatico di database MSSQL su server **Linux o Windows**.

## Architettura

```
Cliente con SQL Server (Linux O Windows)
    ↓
dbshield-agent (Linux systemd | Windows NSSM service)
    ↓
sqlcmd → BACKUP DATABASE
    ↓
file .bak
    ↓
[opzionale: gzip + AES-256-GCM cifratura]
    ↓
Upload via S3/SFTP/FTP/WebDAV
```

## Requisiti sistema

### Server piattaforma (backend Restorix)

- **Solo Linux** (Docker Engine 20.10+ con docker-compose)
- 2 CPU, 4 GB RAM minimo
- Disco: dipende da retention licenze + audit log
- Porte: 80, 443 (nginx); 5432 (postgres interno); 6379 (redis interno)

> Nota: l'auto-installazione tramite Docker Desktop su Windows host **non è supportata** a causa di limitazioni Unix socket WSL2 nei container helper (nginx-reload, certbot). Vedi `docker-compose.yml` linea 50.

### Server agent (dove gira l'agent + SQL Server)

| OS | Versioni supportate | Note |
|----|---------------------|------|
| Linux | Ubuntu 20.04+, Debian 11+, RHEL/Rocky 8+ | Auto-detect SQL Server locale |
| Windows | 10/11, Server 2016/2019/2022/2025 | Richiede `tar.exe` (incluso da Win 10 1803+) |

Per SQL Server (in entrambi i casi):
- SQL Server 2016+ (qualsiasi edition: Express, Standard, Enterprise, Developer)
- `sqlcmd` (ODBC 18+) nel PATH — vedi guide install per setup

## Quick Start (Development)

### Prerequisiti
- Docker + Docker Compose
- Git

### Setup

```bash
# 1. Clona il repository
git clone <repo-url>
cd MSSQL_GUI

# 2. Configura le variabili d'ambiente
cp .env.example .env
# Modifica .env con i tuoi valori — genera chiavi sicure:
# python -c "import secrets; print(secrets.token_hex(32))"

# 3. Avvia lo stack di sviluppo
make dev

# 4. Applica le migrazioni del database
make migrate

# 5. Crea l'utente amministratore iniziale
docker compose exec api python scripts/create_admin.py
```

L'interfaccia web sarà disponibile su:
- Frontend: http://localhost:5173
- API: http://localhost:8000
- Swagger UI (solo development): http://localhost:8000/api/docs

### Comandi utili

```bash
make dev       # Avvia stack completo in modalità sviluppo
make test      # Esegui test backend
make migrate   # Applica migrazioni database
make logs      # Mostra log del servizio API
make shell     # Apri shell nel container API
make down      # Ferma tutti i servizi
```

## Installazione agente sui server client

L'agente Restorix gira su **Linux** o **Windows** in base al server target.

### Linux (Ubuntu 20.04+, Debian 11+, RHEL/Rocky 8+)

One-liner installazione:

```bash
curl -sSL https://backupdb.edminformatica.it/install.sh | sudo bash -s -- --token=<AGENT_TOKEN>
```

Vedi anche: [`docs/agent-linux-install.md`](docs/agent-linux-install.md)

### Windows (10/11 + Server 2016/2019/2022/2025)

In PowerShell **come Amministratore**:

```powershell
$Env:AGENT_TOKEN = "<AGENT_TOKEN>"
irm https://backupdb.edminformatica.it/api/v1/agent/install-script-windows | iex
```

Vedi anche: [`docs/agent-windows-install.md`](docs/agent-windows-install.md)

Il token agente si genera dal pannello web (Servers → Aggiungi).

## Stack tecnologico

| Layer | Tecnologia |
|-------|-----------|
| Backend API | Python 3.11, FastAPI, SQLAlchemy 2.x, Alembic |
| Task queue | Celery + Redis |
| Database | PostgreSQL 15 |
| Frontend | React 18, Vite, TypeScript, Tailwind CSS, shadcn/ui |
| Autenticazione | JWT, bcrypt, TOTP (2FA) |
| Cifratura | AES-256-GCM |
| Agente | Python 3.9+ (Linux) o 3.11 embedded (Windows), boto3, paramiko, requests |
| Infrastruttura | Docker, Docker Compose, Nginx |

## Struttura del progetto

```
MSSQL_GUI/
├── backend/               # API FastAPI + worker Celery
├── frontend/              # SPA React
├── agent/
│   ├── dbshield_agent/    # Package Python cross-platform
│   ├── install.sh             # Installer Linux (bash)
│   ├── install.ps1            # Installer Windows (PowerShell + NSSM)
│   ├── uninstall.ps1          # Uninstaller Windows
│   ├── dbshield-agent.service # Unit systemd (Linux)
│   └── tests/                 # Test pytest
├── nginx/                 # Configurazione reverse proxy
├── docs/                  # Specifiche e piani di implementazione
├── docker-compose.yml
└── Makefile
```

## Licenza

Proprietaria — © 2026 EDM Informatica
