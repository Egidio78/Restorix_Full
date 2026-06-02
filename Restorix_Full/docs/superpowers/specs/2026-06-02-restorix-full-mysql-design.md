# Restorix Full — Design Spec v1.4.0: MySQL Support

**Data:** 2026-06-02  
**Stato:** Approvato  
**Repo:** https://github.com/Egidio78/Restorix_Full.git  
**Server deploy:** egidio@46.225.106.181 — `/opt/restorix/`  
**DNS:** restorix.edminformatica.it  

---

## Contesto

Restorix Full è un nuovo repo indipendente basato sul codice di `Backup_Machine` (v1.3.0), con il sistema licenze rimosso (uso personale). Su questa base viene implementato il supporto backup **MySQL/MariaDB** (v1.4.0).

### Cosa viene copiato da Backup_Machine

Tutto il codice di `Backup_Machine` ad eccezione del sistema licenze (Piano 7):

**Incluso:**
- Backend FastAPI completo (auth 2FA, MSSQL, folder backup, restore, audit, retention, rebrand Restorix)
- Agente Python (executor, discovery MSSQL, storage uploaders S3/SFTP/FTP/WebDAV, install.sh)
- Frontend React (Dashboard, Servers, Jobs, Logs, Audit, Restore Hub, Settings)
- Docker Compose + nginx

**Escluso (licensing):**
- `backend/app/core/license.py` e `public_key.py`
- `backend/app/services/license_guard.py` e `license_notifications.py`
- `backend/app/api/v1/license.py`
- `backend/app/models/license.py`
- `backend/alembic/versions/0010_demo_install.py`
- Frontend: `useLicenseStatus` hook, `LicenseBanner`, tab Licenza in Settings, `PageLocked`
- Celery task `check_license_expiry`
- Middleware license check sulle route API

---

## Requisiti v1.4.0 — MySQL Support

### Requisiti Funzionali

1. Un Server può essere dichiarato di tipo `mssql` o `mysql` al momento della creazione.
2. Il form UI mostra placeholder porta differenti (1433 per MSSQL, 3306 per MySQL) e label campo connessione differenti in base al tipo selezionato.
3. La Discovery database per server MySQL usa `mysql` CLI (`SHOW DATABASES`), filtrando i DB di sistema.
4. Il backup MySQL produce sempre un file `.sql.gz` via pipeline `mysqldump | gzip` (nessun file intermedio su disco).
5. `mysqldump` è invocato con `--single-transaction --routines --triggers` per consistenza e completezza.
6. Il toggle `compression_enabled` è ignorato per job MySQL (sempre gzip).
7. Il toggle `mssql_native_compression` non è mostrato in UI per job MySQL.
8. Cifratura AES-256-GCM opzionale applicata dopo la compressione (identico a MSSQL/folder).
9. Upload verso tutte le destinazioni storage esistenti (S3, SFTP, FTP, WebDAV) — nessuna modifica agli uploader.
10. Il wizard creazione job mostra l'opzione MySQL solo se il server selezionato ha `engine=mysql`.
11. Restore MySQL: fuori scope v1.4.0 — rimandato a v1.4.1.
12. MySQL e MSSQL condividono i limiti di licenza (non applicabili in questa versione uso personale).

### Requisiti Non Funzionali

- Nessuna regressione su backup MSSQL e folder esistenti.
- Migration 0011 non distruttiva: tutti i server/DB esistenti conservati con `engine=mssql`.
- L'agente verifica presenza di `mysql` e `mysqldump` all'avvio se il server è MySQL.

---

## Architettura

### Decisioni Chiave

| Decisione | Scelta | Motivazione |
|-----------|--------|-------------|
| Campo engine | Su `Server` (non `DbInstance`) | Un server ha un motore, tutti i suoi DB ereditano l'engine |
| Campo connessione | Rinomina `mssql_instance` → `connection_string` | Generico, dati preservati, migration non distruttiva |
| BackupType | Aggiunge `mysql` all'enum | Coerente con pattern esistente (folder, mssql) |
| Discovery MySQL | `mysql` CLI | Zero dipendenze Python extra, coerente con sqlcmd |
| Output backup | `.sql.gz` sempre | mysqldump pipe gzip = standard industry, no file temporanei grandi |
| Strategia implementazione | Branch nell'executor esistente | Minimo rischio regressioni, stesso pattern folder_backup |

---

## Database Schema

### Migration 0011

```sql
-- Aggiunta engine a servers (default mssql per backward compat)
ALTER TABLE servers ADD COLUMN engine VARCHAR(20) NOT NULL DEFAULT 'mssql';

-- Rinomina campo generico
ALTER TABLE db_instances RENAME COLUMN mssql_instance TO connection_string;

-- Aggiunta valore MySQL all'enum (non distruttivo in Postgres)
ALTER TYPE backuptype ADD VALUE 'mysql';
```

### Modello Server (aggiornato)

```python
engine: Mapped[str] = mapped_column(String(20), nullable=False, default="mssql")
# valori: "mssql" | "mysql"
```

### Modello DbInstance (aggiornato)

```python
connection_string: Mapped[str] = mapped_column(String(255), nullable=False)
# MSSQL: "SERVERNAME\INSTANCE" o "host,port"
# MySQL: "host:port" es. "db.example.com:3306"
```

### BackupType enum (aggiornato)

```python
class BackupType(str, enum.Enum):
    mssql = "mssql"
    folder = "folder"
    mysql = "mysql"   # nuovo
```

---

## Agente Python

### File Nuovo: `agent/dbshield_agent/mysql_runner.py`

```python
def discover_mysql_databases(host: str, port: int, username: str, password: str) -> tuple[list[str], str | None]:
    """Esegue SHOW DATABASES via mysql CLI, filtra DB di sistema."""

def create_mysql_backup(host: str, port: int, db_name: str, username: str, password: str, temp_dir: str) -> str:
    """mysqldump --single-transaction --routines --triggers | gzip → .sql.gz"""
```

**Sistema DB filtrati dalla discovery:**
`information_schema`, `performance_schema`, `mysql`, `sys`

**Comando backup (pipeline, no file intermedio):**
```bash
mysqldump -h host -P port -u user -ppass \
  --single-transaction --routines --triggers db_name \
  | gzip > /tmp/restorix/db_name_YYYYMMDD_HHMMSS.sql.gz
```

**Gestione errori:**
- `mysqldump` not found → eccezione chiara ("mysqldump not installed")
- Exit code non-zero → eccezione con stderr
- Timeout: 2 ore (stesso di MSSQL per DB grandi)

### Modifiche `executor.py`

```python
elif backup_type == "mysql":
    from dbshield_agent.mysql_runner import create_mysql_backup
    host, port = parse_connection_string(job["connection_string"])
    backup_file = create_mysql_backup(
        host=host, port=port,
        db_name=job["db_name"],
        username=job.get("db_username", ""),
        password=job.get("db_password", ""),
        temp_dir=config.temp_dir,
    )
    already_compressed = True  # sempre .sql.gz
```

### Modifiche `main.py` (discovery loop)

```python
discovery_req = client.get_discovery_request()
if discovery_req:
    engine = discovery_req.get("engine", "mssql")
    if engine == "mysql":
        from dbshield_agent.mysql_runner import discover_mysql_databases
        host, port = parse_connection_string(discovery_req["connection_string"])
        dbs, err = discover_mysql_databases(host, port, ...)
    else:
        from dbshield_agent.discovery import discover_databases
        dbs, err = discover_databases(discovery_req["connection_string"], ...)
    client.report_discovery(dbs, err)
```

### Modifiche `install.sh`

Aggiunta verifica/installazione client MySQL:
```bash
if ! command -v mysqldump &>/dev/null; then
    apt-get install -y default-mysql-client 2>/dev/null || \
    yum install -y mysql 2>/dev/null || \
    echo "WARNING: mysqldump not found. MySQL backups will fail."
fi
```

### Helper `parse_connection_string`

Funzione condivisa nel package agente:
```python
def parse_connection_string(cs: str) -> tuple[str, int]:
    """
    MySQL: "host:port" → ("host", port)
    MSSQL: "SERVER\\INSTANCE" → invariato (non usato per MySQL)
    Default port MySQL: 3306
    """
```

---

## Backend API

### Payload Discovery (agent endpoint)

`GET /api/v1/agent/discovery` aggiunge `engine` nel payload:
```json
{
  "engine": "mysql",
  "connection_string": "db.example.com:3306",
  "username": "...",
  "password": "..."
}
```

### Payload Job (agent endpoint)

`GET /api/v1/agent/jobs` aggiunge per job MySQL:
```json
{
  "backup_type": "mysql",
  "connection_string": "db.example.com:3306",
  "db_name": "mydb",
  "db_username": "root",
  "db_password": "..."
}
```

### Schemas aggiornati

- `ServerCreate` / `ServerOut`: aggiunge campo `engine: str = "mssql"`
- `DbInstanceCreate` / `DbInstanceOut`: rinomina `mssql_instance` → `connection_string`
- `BackupJobOut`: `backup_type` ora può valere `"mysql"`

---

## Frontend

### `Servers.tsx` — Form Aggiungi/Modifica Server

- Nuovo dropdown `Tipo database`: `MSSQL` (default) / `MySQL`
- Al cambio:
  - Porta default: `1433` → `3306`
  - Label campo connessione: `Istanza SQL Server (es. NOME\SQLEXPRESS)` → `Host:Porta (es. 192.168.1.10:3306)`
- Badge engine visibile nella card server (chip `MSSQL` / `MySQL`)

### `Servers.tsx` — Modal Discovery

- Per server MySQL: campo input mostra placeholder `Host:Porta` invece di `Istanza SQL Server`
- Label del modal: `Scopri database MySQL` invece di `Scopri database SQL Server`

### `Jobs.tsx` — Wizard Creazione Job

- Step "Tipo backup":
  - Opzione `MySQL` aggiunta accanto a `MSSQL` e `Cartella`
  - Se il server selezionato ha `engine=mysql`: solo `MySQL` e `Cartella` abilitati
  - Se il server ha `engine=mssql`: solo `MSSQL` e `Cartella` abilitati
- Step "Opzioni":
  - Per job MySQL: `Compressione gzip` non mostrata (sempre attiva, inclusa nel file `.sql.gz`)
  - Per job MySQL: `Compressione nativa MSSQL` non mostrata
  - Etichetta file output: mostra `.sql.gz` per MySQL, `.bak` per MSSQL, `.tar.gz` per folder

### Pagine invariate

Logs, Audit, RestoreHub, Dashboard, Settings, Storage — nessuna modifica necessaria (engine-agnostic).

---

## Deploy

### Struttura directory server

```
/opt/restorix/
├── backend/
├── frontend/
├── agent/
├── nginx/
├── docker-compose.yml
├── .env
└── restore-tmp/
```

### Docker Compose

Stack identico a Backup_Machine:
- `api` — FastAPI + Uvicorn
- `worker` — Celery worker
- `scheduler` — Celery beat
- `db` — PostgreSQL 15
- `redis` — Redis 7
- `frontend` — nginx SPA

Network dedicato `restorix_default` — isolato da `openhuman_default`.

### nginx (container dedicato)

- Porte 80/443 su host
- SSL Let's Encrypt per `restorix.edminformatica.it`
- Proxy `/api/` → container `api:8000`
- Serve SPA frontend su `/`
- Serve `install.sh` e tarball agente su `/install.sh` e `/agent/`

### GitHub

Remote: `https://github.com/Egidio78/Restorix_Full.git`  
Branch principale: `main`

---

## Piano di implementazione (alto livello)

### Piano 8a — Copia base + rimozione licensing

1. Copia codice da `D:\Claude_Code\Backup_Machine\` a `D:\Claude_Code\Restorix_Full\`
2. Rimozione file licensing
3. Rimozione riferimenti licensing da middleware, Celery, frontend
4. Verifica build pulita
5. Push su GitHub `Restorix_Full`

### Piano 8b — MySQL Support

1. Migration 0011 (engine, connection_string, backuptype mysql)
2. Modelli backend aggiornati + schemas
3. `mysql_runner.py` agente (discovery + backup)
4. `executor.py` + `main.py` agente aggiornati
5. `install.sh` aggiornato
6. API agent endpoints aggiornati (payload engine)
7. Frontend Servers.tsx (dropdown engine, modal discovery)
8. Frontend Jobs.tsx (wizard MySQL)
9. Deploy su `46.225.106.181:/opt/restorix/`
10. Test E2E con container MySQL di test

### Piano 8c — Infrastruttura deploy

1. Setup `/opt/restorix/` sul server
2. Docker Compose up
3. nginx + SSL Let's Encrypt per `restorix.edminformatica.it`
4. Agente installato su server di test con MySQL
5. Smoke test end-to-end

---

## Out of Scope v1.4.0

- Restore guidato MySQL (→ v1.4.1)
- PostgreSQL (→ v1.5.0)
- MongoDB / NoSQL (fuori scope prodotto)
- Sistema licenze (rimosso — uso personale)
