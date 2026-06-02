# Piano 8b — MySQL Support (v1.4.0)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementare il supporto backup MySQL/MariaDB in Restorix: discovery database, backup via `mysqldump | gzip`, wizard job UI, migration schema.

**Architecture:** Aggiunta del campo `engine` al modello `Server`, rinomina `mssql_instance` → `connection_string` in `DbInstance`, nuovo valore `mysql` in `BackupType`. Lato agente: nuovo modulo `mysql_runner.py` con discovery e backup, l'executor fa branch su `backup_type == "mysql"`. Lato frontend: dropdown engine nel form server, opzione MySQL nel wizard job.

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy 2.x / Alembic / React 18 / TypeScript / subprocess (mysql CLI / mysqldump)

**Prerequisito:** Piano 8a completato — il codice base è in `Restorix_Full/` e il repo GitHub è configurato.

---

## File Map

**Creati:**
- `backend/alembic/versions/0011_mysql_support.py`
- `agent/dbshield_agent/mysql_runner.py`

**Modificati:**
- `backend/app/models/server.py` — aggiunge campo `engine`
- `backend/app/models/db_instance.py` — rinomina `mssql_instance` → `connection_string`
- `backend/app/models/backup_job.py` — aggiunge `BackupType.mysql`
- `backend/app/schemas/server.py` — aggiunge `engine`
- `backend/app/schemas/db_instance.py` (o server.py se i schema DB instance sono lì) — rinomina campo
- `backend/app/api/v1/agent.py` — aggiunge `engine` nel payload discovery e job
- `backend/app/services/discovery.py` — passa `engine` nel payload Redis
- `agent/dbshield_agent/executor.py` — aggiunge branch `mysql`
- `agent/dbshield_agent/main.py` — discovery branch per engine
- `agent/install.sh` — verifica/installa mysql-client
- `frontend/src/pages/Servers.tsx` — dropdown engine, placeholder dinamici
- `frontend/src/pages/Jobs.tsx` — opzione MySQL nel wizard

---

### Task 1: Migration Alembic 0011

**Files:**
- Create: `backend/alembic/versions/0011_mysql_support.py`

- [ ] **Step 1: Crea il file migration**

```python
# backend/alembic/versions/0011_mysql_support.py
"""mysql_support

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-02

"""
from alembic import op
import sqlalchemy as sa

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Aggiunge engine a servers (default 'mssql' per backward compat)
    op.add_column('servers', sa.Column('engine', sa.String(20), nullable=False, server_default='mssql'))

    # Rinomina mssql_instance → connection_string in db_instances
    op.alter_column('db_instances', 'mssql_instance', new_column_name='connection_string')

    # Aggiunge valore 'mysql' all'enum backuptype (non distruttivo in Postgres)
    op.execute("ALTER TYPE backuptype ADD VALUE IF NOT EXISTS 'mysql'")


def downgrade() -> None:
    op.alter_column('db_instances', 'connection_string', new_column_name='mssql_instance')
    op.drop_column('servers', 'engine')
    # Nota: non si può rimuovere un valore da un enum Postgres senza ricreare il tipo
```

> **Nota:** Se la migration precedente è `0010`, usa `down_revision = '0010'`. Se il Piano 7 è stato rimosso e l'ultima migration è `0009`, usa `down_revision = '0009'`. Verifica con:
> ```bash
> ls /d/Claude_Code/Restorix_Full/backend/alembic/versions/
> ```

- [ ] **Step 2: Commit migration**

```bash
cd /d/Claude_Code/Restorix_Full
git add backend/alembic/versions/0011_mysql_support.py
git commit -m "feat: add migration 0011 for MySQL support (engine, connection_string, backuptype)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push
```

---

### Task 2: Aggiorna modelli SQLAlchemy

**Files:**
- Modify: `backend/app/models/server.py`
- Modify: `backend/app/models/db_instance.py`
- Modify: `backend/app/models/backup_job.py`

- [ ] **Step 1: Aggiorna server.py**

Aggiungi il campo `engine` al modello `Server`:

```python
# backend/app/models/server.py
import uuid
import secrets
from sqlalchemy import String, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin
import enum


class AgentStatus(str, enum.Enum):
    never_connected = "never_connected"
    online = "online"
    offline = "offline"


class Server(Base, TimestampMixin):
    __tablename__ = "servers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    engine: Mapped[str] = mapped_column(String(20), nullable=False, default="mssql")
    agent_token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True,
        default=lambda: secrets.token_hex(32)
    )
    agent_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[AgentStatus] = mapped_column(
        SAEnum(AgentStatus, name="agentstatus", create_type=False),
        nullable=False,
        default=AgentStatus.never_connected,
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    db_instances: Mapped[list["DbInstance"]] = relationship(
        "DbInstance", back_populates="server", cascade="all, delete-orphan"
    )
    backup_jobs: Mapped[list["BackupJob"]] = relationship(
        "BackupJob", back_populates="server"
    )
```

- [ ] **Step 2: Aggiorna db_instance.py**

Rinomina `mssql_instance` → `connection_string`:

```python
# backend/app/models/db_instance.py
import uuid
from sqlalchemy import String, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, TimestampMixin


class DbInstance(Base, TimestampMixin):
    __tablename__ = "db_instances"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    connection_string: Mapped[str] = mapped_column(String(255), nullable=False)
    credentials_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    server: Mapped["Server"] = relationship("Server", back_populates="db_instances")
    backup_jobs: Mapped[list["BackupJob"]] = relationship(
        "BackupJob", back_populates="db_instance"
    )
```

- [ ] **Step 3: Aggiorna backup_job.py**

Aggiungi `mysql` all'enum `BackupType`:

```python
class BackupType(str, enum.Enum):
    mssql = "mssql"
    folder = "folder"
    mysql = "mysql"
```

- [ ] **Step 4: Cerca e aggiorna tutti i riferimenti a mssql_instance negli schemi e API**

```bash
grep -rn "mssql_instance" /d/Claude_Code/Restorix_Full/backend/ --include="*.py"
```

Per ogni file trovato, rinomina `mssql_instance` → `connection_string`.

- [ ] **Step 5: Commit modelli**

```bash
cd /d/Claude_Code/Restorix_Full
git add backend/app/models/server.py backend/app/models/db_instance.py backend/app/models/backup_job.py
git add backend/app/schemas/
git commit -m "feat: update models for MySQL support (engine, connection_string, BackupType.mysql)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push
```

---

### Task 3: Aggiorna API agente (payload discovery e job)

**Files:**
- Modify: `backend/app/api/v1/agent.py`
- Modify: `backend/app/services/discovery.py`

- [ ] **Step 1: Trova gli endpoint di discovery e job in agent.py**

```bash
grep -n "discovery\|mssql_instance\|db_name\|backup_type" /d/Claude_Code/Restorix_Full/backend/app/api/v1/agent.py | head -30
```

- [ ] **Step 2: Aggiorna il payload discovery**

Nell'endpoint `GET /agent/discovery` (o equivalente), aggiungi `engine` e usa `connection_string` invece di `mssql_instance`. Il payload inviato all'agente deve essere:

```python
{
    "engine": server.engine,               # "mssql" | "mysql"
    "connection_string": db_instance.connection_string,
    "username": credentials.get("username", ""),
    "password": credentials.get("password", ""),
}
```

- [ ] **Step 3: Aggiorna il payload job**

Nel serializzatore del job (endpoint `GET /agent/jobs`), aggiungi per i job di tipo `mssql` e `mysql`:

```python
# Per backup_type == "mssql" o "mysql"
payload["connection_string"] = db_instance.connection_string
payload["db_engine"] = server.engine

# Rimuovi o rinomina il vecchio campo mssql_instance se presente
```

- [ ] **Step 4: Aggiorna discovery service**

In `backend/app/services/discovery.py`, nel punto in cui si scrive la request su Redis, aggiungi il campo `engine`:

```python
discovery_payload = {
    "engine": server.engine,
    "connection_string": db_instance.connection_string if db_instance else request_data.get("connection_string"),
    "username": ...,
    "password": ...,
}
```

- [ ] **Step 5: Verifica nessun riferimento residuo a mssql_instance**

```bash
grep -rn "mssql_instance" /d/Claude_Code/Restorix_Full/backend/ --include="*.py"
```

Output atteso: nessuna riga.

- [ ] **Step 6: Commit**

```bash
cd /d/Claude_Code/Restorix_Full
git add backend/app/api/v1/agent.py backend/app/services/discovery.py
git commit -m "feat: add engine and connection_string to agent discovery/job payloads

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push
```

---

### Task 4: Crea mysql_runner.py nell'agente

**Files:**
- Create: `agent/dbshield_agent/mysql_runner.py`

- [ ] **Step 1: Crea il file**

```python
# agent/dbshield_agent/mysql_runner.py
"""MySQL backup and discovery via mysql/mysqldump CLI."""
import logging
import os
import subprocess
from datetime import datetime

logger = logging.getLogger(__name__)

_SYSTEM_DBS = {"information_schema", "performance_schema", "mysql", "sys"}


def _parse_host_port(connection_string: str) -> tuple[str, int]:
    """Parse 'host:port' → (host, port). Default port: 3306."""
    if ":" in connection_string:
        host, port_str = connection_string.rsplit(":", 1)
        try:
            return host.strip(), int(port_str.strip())
        except ValueError:
            pass
    return connection_string.strip(), 3306


def discover_mysql_databases(connection_string: str, username: str, password: str) -> tuple[list[str], str | None]:
    """Return list of user database names on the MySQL server."""
    host, port = _parse_host_port(connection_string)

    cmd = ["mysql", "-h", host, "-P", str(port), "--connect-timeout=10"]
    if username:
        cmd += ["-u", username, f"-p{password}"]
    cmd += ["--batch", "--skip-column-names", "-e", "SHOW DATABASES;"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return [], f"mysql failed: {result.stderr.strip() or result.stdout.strip()}"
        databases = [
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip() and line.strip().lower() not in _SYSTEM_DBS
        ]
        return databases, None
    except FileNotFoundError:
        return [], "mysql client not installed on this server"
    except subprocess.TimeoutExpired:
        return [], "mysql discovery timed out (30s)"
    except Exception as e:
        return [], f"Discovery error: {e}"


def create_mysql_backup(
    connection_string: str,
    db_name: str,
    username: str,
    password: str,
    temp_dir: str,
) -> str:
    """Run mysqldump | gzip and return path to .sql.gz file."""
    host, port = _parse_host_port(connection_string)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_name = db_name.replace(" ", "_").replace("/", "_")
    out_path = os.path.join(temp_dir, f"{safe_name}_{timestamp}.sql.gz")

    dump_cmd = [
        "mysqldump",
        "-h", host,
        "-P", str(port),
        "--single-transaction",
        "--routines",
        "--triggers",
        "--connect-timeout=10",
    ]
    if username:
        dump_cmd += ["-u", username, f"-p{password}"]
    dump_cmd.append(db_name)

    gzip_cmd = ["gzip", "-c"]

    logger.info("Starting MySQL backup: %s/%s → %s", host, db_name, out_path)

    try:
        with open(out_path, "wb") as out_file:
            dump_proc = subprocess.Popen(
                dump_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            gzip_proc = subprocess.Popen(
                gzip_cmd,
                stdin=dump_proc.stdout,
                stdout=out_file,
                stderr=subprocess.PIPE,
            )
            dump_proc.stdout.close()  # allow dump_proc to receive SIGPIPE if gzip exits

            gzip_proc.wait(timeout=7200)  # 2 ore max
            dump_proc.wait(timeout=10)

        if dump_proc.returncode != 0:
            stderr = dump_proc.stderr.read().decode(errors="replace")
            raise RuntimeError(f"mysqldump failed (exit {dump_proc.returncode}): {stderr.strip()}")

        if gzip_proc.returncode != 0:
            raise RuntimeError(f"gzip failed (exit {gzip_proc.returncode})")

        size = os.path.getsize(out_path)
        logger.info("MySQL backup completed: %s (%.1f MB)", out_path, size / 1024 / 1024)
        return out_path

    except Exception:
        # Cleanup partial file on failure
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except OSError:
                pass
        raise
```

- [ ] **Step 2: Verifica import e sintassi**

```bash
cd /d/Claude_Code/Restorix_Full/agent
python -c "from dbshield_agent.mysql_runner import create_mysql_backup, discover_mysql_databases; print('OK')"
```

Output atteso: `OK`

- [ ] **Step 3: Commit**

```bash
cd /d/Claude_Code/Restorix_Full
git add agent/dbshield_agent/mysql_runner.py
git commit -m "feat: add mysql_runner.py with discovery and backup via CLI pipeline

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push
```

---

### Task 5: Aggiorna executor.py e main.py dell'agente

**Files:**
- Modify: `agent/dbshield_agent/executor.py`
- Modify: `agent/dbshield_agent/main.py`

- [ ] **Step 1: Aggiorna executor.py**

Nel metodo `execute_job`, aggiungi il branch MySQL dopo il branch folder:

```python
def execute_job(job: dict, config: AgentConfig, client: AgentClient) -> None:
    run_id = job["run_id"]
    backup_type = job.get("backup_type", "mssql")
    backup_file = None

    try:
        if backup_type == "folder":
            folder = job.get("folder_path")
            if not folder:
                raise RuntimeError("folder_path missing for folder backup")
            backup_file = create_folder_backup(folder, config.temp_dir, job.get("job_name", "folder"))
            already_compressed = True

        elif backup_type == "mysql":
            from dbshield_agent.mysql_runner import create_mysql_backup
            connection_string = job.get("connection_string", "")
            if not connection_string:
                raise RuntimeError("connection_string missing for MySQL backup")
            backup_file = create_mysql_backup(
                connection_string=connection_string,
                db_name=job["db_name"],
                username=job.get("db_username", ""),
                password=job.get("db_password", ""),
                temp_dir=config.temp_dir,
            )
            already_compressed = True  # sempre .sql.gz

        else:
            # mssql (default)
            native = job.get("mssql_native_compression", False)
            backup_file = create_backup(
                mssql_instance=job.get("connection_string") or job.get("mssql_instance", ""),
                db_name=job["db_name"],
                username=job.get("db_username", ""),
                password=job.get("db_password", ""),
                temp_dir=config.temp_dir,
                native_compression=native,
            )
            already_compressed = native

        if job.get("compression_enabled") and not already_compressed:
            backup_file = compress_file(backup_file)

        if job.get("encryption_enabled") and job.get("encryption_password"):
            backup_file = encrypt_file(backup_file, job["encryption_password"])

        checksum = sha256_file(backup_file)
        size_bytes = os.path.getsize(backup_file)
        remote_name = os.path.basename(backup_file)

        uploader = get_uploader(job["storage_type"], job["storage_config"])
        remote_path = uploader.upload(backup_file, remote_name)

        client.report_success(run_id=run_id, size_bytes=size_bytes, file_path=remote_path, checksum=checksum)
        logger.info(f"Job {run_id} completed successfully: {remote_path}")

    except Exception as e:
        logger.error(f"Job {run_id} failed: {e}")
        client.report_failure(run_id=run_id, error_message=str(e))

    finally:
        if backup_file and os.path.exists(backup_file):
            try:
                os.remove(backup_file)
            except Exception:
                pass
```

- [ ] **Step 2: Aggiorna main.py — discovery loop**

Nel blocco che gestisce la `discovery_req`, aggiungi il branch per engine MySQL:

```python
discovery_req = client.get_discovery_request()
if discovery_req:
    engine = discovery_req.get("engine", "mssql")
    connection_string = discovery_req.get("connection_string", "")
    username = discovery_req.get("username", "")
    password = discovery_req.get("password", "")

    if engine == "mysql":
        from dbshield_agent.mysql_runner import discover_mysql_databases
        logger.info(f"MySQL discovery request for {connection_string}")
        dbs, err = discover_mysql_databases(connection_string, username, password)
    else:
        from dbshield_agent.discovery import discover_databases
        logger.info(f"MSSQL discovery request for {connection_string}")
        dbs, err = discover_databases(connection_string, username, password)

    if err:
        logger.error(f"Discovery failed: {err}")
    else:
        logger.info(f"Discovered {len(dbs)} databases: {dbs}")
    client.report_discovery(dbs, err)
```

- [ ] **Step 3: Verifica sintassi**

```bash
cd /d/Claude_Code/Restorix_Full/agent
python -c "from dbshield_agent.executor import execute_job; from dbshield_agent.main import main; print('OK')"
```

Output atteso: `OK`

- [ ] **Step 4: Commit**

```bash
cd /d/Claude_Code/Restorix_Full
git add agent/dbshield_agent/executor.py agent/dbshield_agent/main.py
git commit -m "feat: add MySQL branch in executor and main discovery loop

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push
```

---

### Task 6: Aggiorna install.sh

**Files:**
- Modify: `agent/install.sh`

- [ ] **Step 1: Trova il punto in cui install.sh verifica sqlcmd**

```bash
grep -n "sqlcmd\|mssql\|apt-get\|install" /d/Claude_Code/Restorix_Full/agent/install.sh | head -20
```

- [ ] **Step 2: Aggiungi verifica/installazione mysql-client**

Dopo il blocco di verifica `sqlcmd`, aggiungi:

```bash
# Verifica/installazione mysql client (per backup MySQL)
if ! command -v mysqldump &>/dev/null; then
    echo "mysqldump non trovato. Tentativo installazione default-mysql-client..."
    if command -v apt-get &>/dev/null; then
        apt-get install -y default-mysql-client 2>/dev/null && echo "mysql-client installato." || \
            echo "WARNING: impossibile installare mysql-client. I backup MySQL falliranno."
    elif command -v yum &>/dev/null; then
        yum install -y mysql 2>/dev/null && echo "mysql installato." || \
            echo "WARNING: impossibile installare mysql. I backup MySQL falliranno."
    else
        echo "WARNING: mysqldump non trovato e gestore pacchetti non riconosciuto. I backup MySQL falliranno."
    fi
else
    echo "mysqldump trovato: $(which mysqldump)"
fi
```

- [ ] **Step 3: Commit**

```bash
cd /d/Claude_Code/Restorix_Full
git add agent/install.sh
git commit -m "feat: add mysql-client check and install in install.sh

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push
```

---

### Task 7: Frontend — Servers.tsx (dropdown engine)

**Files:**
- Modify: `frontend/src/pages/Servers.tsx`

- [ ] **Step 1: Aggiungi dropdown engine nel form creazione/modifica server**

Nel form `ServerForm` (o equivalente), aggiungi prima del campo hostname/porta:

```tsx
{/* Tipo database */}
<div className="space-y-2">
  <Label htmlFor="engine">Tipo database</Label>
  <Select value={form.engine ?? "mssql"} onValueChange={(v) => setForm({ ...form, engine: v })}>
    <SelectTrigger id="engine">
      <SelectValue />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="mssql">MSSQL (SQL Server)</SelectItem>
      <SelectItem value="mysql">MySQL / MariaDB</SelectItem>
    </SelectContent>
  </Select>
</div>
```

- [ ] **Step 2: Rendi dinamici il placeholder porta e la label istanza**

```tsx
const isMysql = form.engine === "mysql"

// Porta
<Input
  id="port"
  placeholder={isMysql ? "3306" : "1433"}
  ...
/>

// Campo connessione (istanza per MSSQL, host:porta per MySQL)
<Label htmlFor="connection_string">
  {isMysql ? "Host:Porta (es. 192.168.1.10:3306)" : "Istanza SQL Server (es. NOME\\SQLEXPRESS)"}
</Label>
<Input
  id="connection_string"
  name="connection_string"
  placeholder={isMysql ? "192.168.1.10:3306" : "SERVERNAME\\SQLEXPRESS"}
  ...
/>
```

- [ ] **Step 3: Aggiungi badge engine nella card server**

```tsx
<Badge variant={server.engine === "mysql" ? "secondary" : "outline"}>
  {server.engine === "mysql" ? "MySQL" : "MSSQL"}
</Badge>
```

- [ ] **Step 4: Aggiorna modal discovery**

Nel modale di discovery database, cambia il label del campo in base all'engine del server:

```tsx
<Label>
  {server.engine === "mysql"
    ? "Connessione MySQL (host:porta)"
    : "Istanza SQL Server (es. NOME\\SQLEXPRESS)"}
</Label>
```

- [ ] **Step 5: Aggiorna il tipo ServerFormData e le chiamate API**

Assicurati che l'oggetto inviato alla POST/PATCH `/servers` includa `engine`:
```tsx
const payload = {
  name: form.name,
  hostname: form.hostname,
  engine: form.engine ?? "mssql",
  ...
}
```

- [ ] **Step 6: Commit**

```bash
cd /d/Claude_Code/Restorix_Full
git add frontend/src/pages/Servers.tsx
git commit -m "feat: add engine dropdown and dynamic labels in Servers form

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push
```

---

### Task 8: Frontend — Jobs.tsx (wizard MySQL)

**Files:**
- Modify: `frontend/src/pages/Jobs.tsx`

- [ ] **Step 1: Aggiungi opzione MySQL nel wizard step "Tipo backup"**

Nel componente o sezione dove si sceglie `backup_type`, aggiungi l'opzione MySQL e disabilita tipi non compatibili con l'engine del server:

```tsx
const serverEngine = selectedServer?.engine ?? "mssql"

// Opzione MSSQL — disabilitata se server è MySQL
<label className={serverEngine !== "mssql" ? "opacity-40 cursor-not-allowed" : ""}>
  <input
    type="radio"
    value="mssql"
    disabled={serverEngine !== "mssql"}
    ...
  />
  SQL Server (MSSQL)
</label>

// Opzione MySQL — disabilitata se server è MSSQL
<label className={serverEngine !== "mysql" ? "opacity-40 cursor-not-allowed" : ""}>
  <input
    type="radio"
    value="mysql"
    disabled={serverEngine !== "mysql"}
    ...
  />
  MySQL / MariaDB
</label>

// Opzione Cartella — sempre disponibile
<label>
  <input type="radio" value="folder" ... />
  Cartella filesystem
</label>
```

- [ ] **Step 2: Nascondi opzioni MSSQL-specific per job MySQL**

```tsx
{/* Mostra solo se backup_type == "mssql" */}
{form.backupType === "mssql" && (
  <div>
    <Label>Compressione nativa SQL Server</Label>
    <Switch checked={form.mssqlNativeCompression} ... />
  </div>
)}

{/* Mostra solo se backup_type != "mysql" (mysql usa sempre gzip) */}
{form.backupType !== "mysql" && (
  <div>
    <Label>Compressione gzip</Label>
    <Switch checked={form.compressionEnabled} ... />
  </div>
)}
```

- [ ] **Step 3: Aggiorna etichetta file output**

```tsx
const fileExtension =
  form.backupType === "mysql" ? ".sql.gz" :
  form.backupType === "folder" ? ".tar.gz" :
  ".bak"

<p className="text-sm text-muted-foreground">
  Output: <code>{form.dbName}_{"{timestamp}"}{fileExtension}</code>
</p>
```

- [ ] **Step 4: Commit**

```bash
cd /d/Claude_Code/Restorix_Full
git add frontend/src/pages/Jobs.tsx
git commit -m "feat: add MySQL option in job wizard with engine-aware controls

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push
```

---

### Task 9: Test E2E con container MySQL

- [ ] **Step 1: Aggiungi servizio MySQL al docker-compose.dev.yml**

```yaml
  mysql-test:
    image: mysql:8.0
    container_name: restorix-mysql-test
    environment:
      MYSQL_ROOT_PASSWORD: testpass
      MYSQL_DATABASE: testdb
    ports:
      - "3307:3306"
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-u", "root", "-ptestpass"]
      interval: 10s
      timeout: 5s
      retries: 5
```

- [ ] **Step 2: Avvia lo stack dev**

```bash
cd /d/Claude_Code/Restorix_Full
docker compose -f docker-compose.dev.yml up -d mysql-test
docker compose -f docker-compose.dev.yml ps mysql-test
```

Attendi che lo stato sia `healthy`.

- [ ] **Step 3: Applica la migration 0011**

```bash
docker compose exec api alembic upgrade head
```

Output atteso: `Running upgrade ... -> 0011, mysql_support`

- [ ] **Step 4: Crea un server MySQL dalla UI**

1. Login su http://localhost (o porta dev configurata)
2. Vai su Servers → Aggiungi server
3. Tipo: `MySQL`, hostname: `mysql-test`, porta: `3306`
4. Verifica che la porta default sia 3306 e la label sia "Host:Porta"
5. Salva

- [ ] **Step 5: Esegui discovery database**

1. Sul server MySQL appena creato, clicca "Scopri database"
2. Inserisci `mysql-test:3306`, username `root`, password `testpass`
3. Verifica che appaiano i database (almeno `testdb`)
4. Seleziona `testdb` e salva

- [ ] **Step 6: Crea un job backup MySQL**

1. Vai su Jobs → Nuovo job
2. Seleziona il server MySQL → tipo `MySQL`
3. Seleziona database `testdb`
4. Seleziona storage configurato
5. Salva e clicca "Backup ora"

- [ ] **Step 7: Verifica il backup**

In Logs, verifica che il run mostri stato `success` con file `.sql.gz`.

- [ ] **Step 8: Commit finale e tag**

```bash
cd /d/Claude_Code/Restorix_Full
git add docker-compose.dev.yml
git commit -m "feat: add MySQL test container to dev compose

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git tag v1.4.0
git push
git push --tags
```
