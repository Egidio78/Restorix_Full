# DBShield — MSSQL Backup Manager

Piattaforma SaaS / on-premise per il backup automatico di database MSSQL su server Linux.

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

## Stack tecnologico

| Layer | Tecnologia |
|-------|-----------|
| Backend API | Python 3.11, FastAPI, SQLAlchemy 2.x, Alembic |
| Task queue | Celery + Redis |
| Database | PostgreSQL 15 |
| Frontend | React 18, Vite, TypeScript, Tailwind CSS, shadcn/ui |
| Autenticazione | JWT, bcrypt, TOTP (2FA) |
| Cifratura | AES-256-GCM |
| Infrastruttura | Docker, Docker Compose, Nginx |

## Struttura del progetto

```
MSSQL_GUI/
├── backend/          # API FastAPI + worker Celery
├── frontend/         # SPA React
├── nginx/            # Configurazione reverse proxy
├── docs/             # Specifiche e piani di implementazione
├── docker-compose.yml
└── Makefile
```

## Licenza

Proprietaria — © 2026 EDM Informatica
