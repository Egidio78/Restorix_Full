# Piano 8a — Base Copy & Licensing Removal

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Copiare il codice di Backup_Machine in Restorix_Full/, rimuovere il sistema licenze, configurare il remote GitHub e fare il primo push.

**Architecture:** Copia 1:1 da `D:\Claude_Code\Backup_Machine\` a `D:\Claude_Code\Restorix_Full\`, poi rimozione chirurgica di tutti i file e riferimenti al sistema licenze (Piano 7). Il risultato è un progetto standalone completo (backend, frontend, agente) pronto per ricevere la feature MySQL.

**Tech Stack:** Python 3.11 / FastAPI / SQLAlchemy 2.x / Celery / React 18 / Vite / TypeScript / Docker Compose / Git

---

## File Map

**Copiati da Backup_Machine → Restorix_Full/**
- `backend/` — intero directory (FastAPI app, alembic, tests, scripts)
- `frontend/` — intero directory (React app, Dockerfile)
- `agent/` — intero directory (agente Python, install.sh, build_package.sh)
- `nginx/` — intero directory
- `docker-compose.yml`
- `docker-compose.dev.yml`
- `Makefile`

**Da ELIMINARE dopo la copia:**
- `backend/app/core/license.py`
- `backend/app/core/public_key.py`
- `backend/app/services/license_guard.py`
- `backend/app/services/license_notifications.py`
- `backend/app/api/v1/license.py`
- `backend/app/models/license.py`
- `backend/alembic/versions/0010_demo_install.py`
- `frontend/src/hooks/useLicenseStatus.ts`
- `frontend/src/components/layout/LicenseBanner.tsx`
- `frontend/src/pages/Locked.tsx`
- `frontend/src/lib/license.ts`

**Da MODIFICARE:**
- `backend/app/main.py` — rimuovi `LockedStateMiddleware` e `initialize_demo_license`
- `backend/app/api/v1/router.py` — rimuovi import e `include_router` license
- `backend/app/celery_app.py` — rimuovi beat schedule `check_license_expiry`
- `backend/app/tasks.py` — rimuovi task `check_license_expiry` e helper `_check_license_expiry_async`
- `frontend/src/components/layout/AppLayout.tsx` — rimuovi `LicenseBanner` e `useLicenseStatus`
- `frontend/src/pages/Settings.tsx` — rimuovi tab `licenza` e funzione `LicenseTab`

---

### Task 1: Copia il codice da Backup_Machine

**Files:**
- Create: `Restorix_Full/backend/`, `Restorix_Full/frontend/`, `Restorix_Full/agent/`, `Restorix_Full/nginx/`

- [ ] **Step 1: Copia le directory principali**

```bash
cp -r /d/Claude_Code/Backup_Machine/backend /d/Claude_Code/Restorix_Full/
cp -r /d/Claude_Code/Backup_Machine/frontend /d/Claude_Code/Restorix_Full/
cp -r /d/Claude_Code/Backup_Machine/agent /d/Claude_Code/Restorix_Full/
cp -r /d/Claude_Code/Backup_Machine/nginx /d/Claude_Code/Restorix_Full/
cp /d/Claude_Code/Backup_Machine/docker-compose.yml /d/Claude_Code/Restorix_Full/
cp /d/Claude_Code/Backup_Machine/docker-compose.dev.yml /d/Claude_Code/Restorix_Full/
cp /d/Claude_Code/Backup_Machine/Makefile /d/Claude_Code/Restorix_Full/
```

- [ ] **Step 2: Verifica struttura copiata**

```bash
ls /d/Claude_Code/Restorix_Full/
```

Output atteso:
```
agent/  backend/  docs/  docker-compose.yml  docker-compose.dev.yml  frontend/  Makefile  nginx/
```

- [ ] **Step 3: Verifica che i file chiave esistano**

```bash
ls /d/Claude_Code/Restorix_Full/backend/app/main.py
ls /d/Claude_Code/Restorix_Full/agent/dbshield_agent/executor.py
ls /d/Claude_Code/Restorix_Full/frontend/src/pages/Dashboard.tsx
```

Tutti e tre devono esistere senza errori.

---

### Task 2: Rimuovi file licensing

**Files:**
- Delete: tutti i file elencati in "Da ELIMINARE" sopra

- [ ] **Step 1: Elimina file backend licensing**

```bash
rm /d/Claude_Code/Restorix_Full/backend/app/core/license.py
rm /d/Claude_Code/Restorix_Full/backend/app/core/public_key.py
rm /d/Claude_Code/Restorix_Full/backend/app/services/license_guard.py
rm /d/Claude_Code/Restorix_Full/backend/app/services/license_notifications.py
rm /d/Claude_Code/Restorix_Full/backend/app/api/v1/license.py
rm /d/Claude_Code/Restorix_Full/backend/app/models/license.py
rm /d/Claude_Code/Restorix_Full/backend/alembic/versions/0010_demo_install.py
```

- [ ] **Step 2: Elimina file frontend licensing**

```bash
rm /d/Claude_Code/Restorix_Full/frontend/src/hooks/useLicenseStatus.ts
rm /d/Claude_Code/Restorix_Full/frontend/src/components/layout/LicenseBanner.tsx
rm /d/Claude_Code/Restorix_Full/frontend/src/pages/Locked.tsx
rm /d/Claude_Code/Restorix_Full/frontend/src/lib/license.ts
```

- [ ] **Step 3: Verifica eliminazioni**

```bash
ls /d/Claude_Code/Restorix_Full/backend/app/core/
ls /d/Claude_Code/Restorix_Full/backend/app/api/v1/
```

Output atteso per `core/`: `encryption.py  security.py  rate_limit.py  __init__.py` (no `license.py`, no `public_key.py`)
Output atteso per `api/v1/`: no `license.py`

---

### Task 3: Rimuovi riferimenti licensing da main.py

**Files:**
- Modify: `Restorix_Full/backend/app/main.py`

- [ ] **Step 1: Rimuovi LockedStateMiddleware e initialize_demo_license**

Il file `main.py` dopo la modifica deve essere:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.config import get_settings
from app.api.v1.router import router as v1_router
from app.core.rate_limit import limiter

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version='1.0.0',
    docs_url='/api/docs' if settings.app_env != 'production' else None,
    redoc_url=None,
    openapi_url='/openapi.json' if settings.app_env != 'production' else None,
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={'detail': 'Troppe richieste, riprova tra poco.'},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(v1_router, prefix='/api/v1')


@app.get('/api/health')
async def health():
    return {'status': 'ok', 'app': settings.app_name}
```

- [ ] **Step 2: Verifica che main.py non importi nulla da license**

```bash
grep -n "license\|License\|Locked" /d/Claude_Code/Restorix_Full/backend/app/main.py
```

Output atteso: nessuna riga trovata.

---

### Task 4: Rimuovi riferimenti licensing da router, celery, tasks

**Files:**
- Modify: `Restorix_Full/backend/app/api/v1/router.py`
- Modify: `Restorix_Full/backend/app/celery_app.py`
- Modify: `Restorix_Full/backend/app/tasks.py`

- [ ] **Step 1: Aggiorna router.py**

Sostituisci il contenuto di `backend/app/api/v1/router.py` con:

```python
from fastapi import APIRouter
from app.api.v1 import auth, users, servers, storage, jobs, runs, agent, notifications, organizations, audit, restore_hub

router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(servers.router, prefix="/servers", tags=["servers"])
router.include_router(storage.router, prefix="/storage", tags=["storage"])
router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
router.include_router(runs.router, prefix="/runs", tags=["runs"])
router.include_router(agent.router, prefix="/agent", tags=["agent"])
router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
router.include_router(organizations.router, prefix="/organizations", tags=["organizations"])
router.include_router(audit.router, prefix="/audit", tags=["audit"])
router.include_router(restore_hub.router, prefix="/restore-hub", tags=["restore-hub"])
```

- [ ] **Step 2: Rimuovi check_license_expiry dal beat schedule in celery_app.py**

```bash
grep -n "check_license" /d/Claude_Code/Restorix_Full/backend/app/celery_app.py
```

Trova la riga con `check_license_expiry` nel dizionario `beat_schedule` e rimuovi l'intero blocco corrispondente (chiave + valore dict). Salva il file.

- [ ] **Step 3: Rimuovi check_license_expiry da tasks.py**

```bash
grep -n "check_license_expiry\|_check_license_expiry_async" /d/Claude_Code/Restorix_Full/backend/app/tasks.py
```

Rimuovi le funzioni `check_license_expiry` e `_check_license_expiry_async` (tipicamente ~90 righe verso la fine del file).

- [ ] **Step 4: Verifica nessun riferimento residuo al licensing**

```bash
grep -rn "license\|License" /d/Claude_Code/Restorix_Full/backend/app/ --include="*.py" | grep -v "__pycache__"
```

Output atteso: nessuna riga (o solo commenti irrilevanti). Se compaiono import da `app.models.license` o `app.services.license_guard` in altri file, rimuovili.

---

### Task 5: Rimuovi riferimenti licensing dal frontend

**Files:**
- Modify: `Restorix_Full/frontend/src/components/layout/AppLayout.tsx`
- Modify: `Restorix_Full/frontend/src/pages/Settings.tsx`

- [ ] **Step 1: Aggiorna AppLayout.tsx**

Rimuovi le righe:
```tsx
import LicenseBanner from "./LicenseBanner";
import { useLicenseStatus } from "@/hooks/useLicenseStatus";
```
e il blocco:
```tsx
const { data: license } = useLicenseStatus();
// ...
if (license?.state === "LOCKED") { ... }
// ...
<LicenseBanner />
```

Il componente deve continuare a funzionare normalmente senza queste righe (sidebar, header, content slot).

- [ ] **Step 2: Aggiorna Settings.tsx**

Rimuovi:
- `import { useLicenseStatus } from "@/hooks/useLicenseStatus"`
- `import { formatTier } from "@/lib/license"`
- `import type { LicenseHistoryItem } from "@/lib/license"`
- Il tab `licenza` dall'array dei tab (se presente come stringa o oggetto)
- `{tab === "licenza" && isSuperadmin && <LicenseTab />}` dal JSX
- L'intera funzione `LicenseTab()` dal file

- [ ] **Step 3: Verifica nessun riferimento residuo nel frontend**

```bash
grep -rn "license\|License\|Locked\|useLicenseStatus\|LicenseBanner" /d/Claude_Code/Restorix_Full/frontend/src/ --include="*.tsx" --include="*.ts"
```

Output atteso: nessuna riga trovata.

---

### Task 6: Configura GitHub remote e primo push

- [ ] **Step 1: Crea il repo su GitHub (se non esiste)**

Vai su https://github.com/new e crea `Restorix_Full` come repo privato vuoto (no README, no .gitignore). Oppure da CLI se gh è installato:

```bash
gh repo create Egidio78/Restorix_Full --private --description "Restorix — Automated backup platform for MSSQL, MySQL, and folders"
```

- [ ] **Step 2: Configura remote e prepara .gitignore**

```bash
cd /d/Claude_Code/Restorix_Full

# Crea .gitignore
cat > .gitignore << 'EOF'
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
*.egg-info/
dist/
build/
.env
.env.*
!.env.example
*.tar.gz
node_modules/
frontend/dist/
restore-tmp/
*.bak
*.sql
*.sql.gz
.pytest_cache/
.coverage
htmlcov/
EOF
```

- [ ] **Step 3: Aggiungi remote GitHub**

```bash
cd /d/Claude_Code/Restorix_Full
git remote add origin https://github.com/Egidio78/Restorix_Full.git
git remote -v
```

Output atteso:
```
origin  https://github.com/Egidio78/Restorix_Full.git (fetch)
origin  https://github.com/Egidio78/Restorix_Full.git (push)
```

- [ ] **Step 4: Stage e commit di tutto il codice base**

```bash
cd /d/Claude_Code/Restorix_Full
git add backend/ frontend/ agent/ nginx/ docker-compose.yml docker-compose.dev.yml Makefile .gitignore
git commit -m "feat: add Restorix base (Backup_Machine v1.3.0 without licensing)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

- [ ] **Step 5: Push su GitHub**

```bash
cd /d/Claude_Code/Restorix_Full
git push -u origin master
```

- [ ] **Step 6: Verifica push**

```bash
gh repo view Egidio78/Restorix_Full --web
```

Oppure apri https://github.com/Egidio78/Restorix_Full nel browser e verifica che i file siano presenti.

---

### Task 7: Smoke test build locale

- [ ] **Step 1: Verifica che il backend importi senza errori**

```bash
cd /d/Claude_Code/Restorix_Full/backend
python -c "from app.main import app; print('OK')" 2>&1
```

Output atteso: `OK`

Se compaiono `ImportError` su moduli `license`, significa che è rimasto qualche riferimento — trovalo con:
```bash
grep -rn "from app.*license\|import.*license" /d/Claude_Code/Restorix_Full/backend/app/ --include="*.py"
```
e rimuovilo.

- [ ] **Step 2: Verifica che il frontend compili senza errori TypeScript**

```bash
cd /d/Claude_Code/Restorix_Full/frontend
npm install
npx tsc --noEmit 2>&1 | head -20
```

Output atteso: nessun errore TypeScript. Se compaiono errori su `useLicenseStatus` o `LicenseBanner`, mancano ancora delle rimozioni — trovale e correggile.

- [ ] **Step 3: Commit fix eventuali**

```bash
cd /d/Claude_Code/Restorix_Full
git add -A
git commit -m "fix: remove residual licensing references after smoke test

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push
```
