# ansible-inventory-ui — Design Specification
**Data:** 2026-05-16
**Autore:** EDM Informatica — Sistemista

---

## Contesto

Interfaccia web per permettere ai colleghi di aggiungere e gestire server nell'inventory AWX (Ansible Automation Platform) in modo guidato e autonomo, senza accedere direttamente ad AWX. Il sistema sincronizza i dati con una base Airtable esistente e include gestione utenti con ruoli differenziati.

Progetto separato e indipendente da InfraAI.

---

## Obiettivi

- Guidare i colleghi step-by-step nell'inserimento di nuovi server su AWX tramite wizard con menu a tendina
- Rilevare automaticamente i duplicati prima dell'inserimento (hostname già presente)
- Sincronizzare i dati bidirezionalmente con la base Airtable esistente
- Gestire utenti con tre ruoli: Viewer, Editor, Admin
- Girare su una VPS dedicata in Docker

---

## Architettura

### Stack

| Container | Tecnologia | Ruolo |
|---|---|---|
| `frontend` | Next.js 14 (React) | Wizard UI, gestione utenti, lista server |
| `backend` | Python 3.12 + FastAPI | Auth JWT, AWX client, Airtable sync |
| `db` | PostgreSQL 16 | Utenti, sessioni, cache server, audit log |
| Nginx (host) | Nginx | Reverse proxy, SSL Let's Encrypt |

### Diagramma

```
┌─────────────────────────────────────────────────────┐
│              VPS ansible-inventory-ui                │
│                                                      │
│  ┌──────────────┐    ┌───────────────────────┐      │
│  │  Frontend    │    │  Backend              │      │
│  │  Next.js 14  │◄──►│  FastAPI + Python     │      │
│  │  (port 3000) │    │  (port 8000)          │      │
│  └──────────────┘    └──────────┬────────────┘      │
│                                 │                    │
│                    ┌────────────┴───────────┐        │
│                    ▼                        ▼        │
│             ┌────────────┐        ┌──────────────┐  │
│             │ PostgreSQL │        │  Nginx       │  │
│             │ (port 5432)│        │  (proxy+SSL) │  │
│             └────────────┘        └──────────────┘  │
└─────────────────────────────────────────────────────┘
         │                    │
         ▼                    ▼
    AWX API              Airtable API
    (altra VPS)          (cloud)
```

### Flusso principale

```
Collega apre la UI
  │
  ▼
Step 1: Seleziona inventory AWX (menu a tendina, dati live da AWX)
  │
  ▼
Step 2: Inserisce hostname + IP
  │  → al blur: controllo duplicati in tempo reale (DB locale + AWX API)
  │  → badge "Disponibile" ✅ o "Già presente" ❌
  ▼
Step 3: Classifica il server (tutti menu a tendina)
  │  Nome cliente, codice, ambiente, tipo asset, OS, distro, versione,
  │  hypervisor, cluster hypervisor
  ▼
Step 4: Riepilogo + conferma
  │  → checkbox "Sincronizza su Airtable" (default: spuntato)
  │  → pulsante "Aggiungi Server"
  ▼
Backend: aggiunge host su AWX → salva in DB locale → sync Airtable
  │
  ▼
Feedback: progress step-by-step con stato di ogni operazione
```

---

## Modello Dati

### Tabella `servers`

| Campo | Tipo | Note |
|---|---|---|
| `id` | int PK | |
| `hostname` | varchar(255) UNIQUE | chiave per duplicate detection |
| `fqdn` | varchar(255) nullable | |
| `ip` | varchar(45) | IPv4/IPv6 |
| `nome_cliente` | varchar(255) nullable | |
| `codice_cliente` | varchar(50) nullable | es. CL001 |
| `ambiente` | enum | Produzione / Sviluppo / Staging / Test |
| `tipo_asset` | enum | Server Dedicato / VPS / Macchina Virtuale |
| `sistema_operativo` | enum | Linux / Windows |
| `distribuzione_os` | varchar(100) nullable | Ubuntu Server / Debian / Rocky Linux / ecc. |
| `versione_os` | varchar(50) nullable | es. 22.04 LTS |
| `hypervisor` | enum | Proxmox / VMware ESXi / Hyper-V / Nessuno |
| `cluster_hypervisor` | varchar(255) nullable | visibile solo se hypervisor ≠ Nessuno |
| `awx_inventory_id` | int | ID inventory AWX |
| `awx_host_id` | int nullable | ID host AWX (null prima della sync) |
| `airtable_record_id` | varchar(50) nullable | ID record Airtable per sync bidirezionale |
| `created_by` | int FK → users | chi ha inserito il server |
| `created_at` | datetime | |
| `updated_at` | datetime | |

Le variabili aggiuntive vengono salvate anche nel campo `variables` dell'host AWX come YAML:
```yaml
ambiente: Produzione
tipo_asset: Macchina Virtuale
nome_cliente: Centro Cell
codice_cliente: CL007
distribuzione_os: Windows Server
versione_os: 2022 Std
hypervisor: Proxmox
cluster_hypervisor: ClusterA
```

### Tabella `users`

| Campo | Tipo | Note |
|---|---|---|
| `id` | int PK | |
| `username` | varchar(100) UNIQUE | |
| `email` | varchar(255) UNIQUE | |
| `hashed_password` | varchar | bcrypt |
| `role` | enum | viewer / editor / admin |
| `is_active` | bool | default true |
| `totp_secret` | varchar(255) nullable | segreto TOTP cifrato |
| `totp_enabled` | bool | default false |
| `totp_backup_codes` | text nullable | JSON array di codici monouso hashati |
| `created_at` | datetime | |

### Tabella `audit_log`

| Campo | Tipo | Note |
|---|---|---|
| `id` | int PK | |
| `user_id` | int FK | chi ha eseguito l'azione |
| `action` | varchar(50) | create / update / delete / sync_airtable / import_airtable |
| `server_hostname` | varchar(255) | hostname coinvolto |
| `detail` | text | JSON con stato prima/dopo |
| `created_at` | datetime | |

---

## Integrazione AWX

Comunicazione via AWX REST API v2. Token Bearer in `.env`.

| Operazione | Endpoint | Trigger |
|---|---|---|
| Lista inventory | `GET /api/v2/inventories/` | Caricamento Step 1 |
| Verifica duplicato | `GET /api/v2/hosts/?name=<hostname>` | Blur su campo hostname |
| Aggiungi host | `POST /api/v2/hosts/` | Submit wizard |
| Aggiorna host | `PATCH /api/v2/hosts/<id>/` | Modifica dalla lista server |
| Elimina host | `DELETE /api/v2/hosts/<id>/` | Cancellazione (solo Admin) |

---

## Integrazione Airtable

Airtable REST API v0. Token e Base ID in `.env`. Mapping campi 1:1 con la base esistente.

| Operazione | Trigger |
|---|---|
| Export → Airtable | Automatico dopo ogni aggiunta/modifica dalla UI |
| Import ← Airtable | Manuale (pulsante Admin) oppure schedulato ogni notte (cron nel backend) |
| Risoluzione conflitti | Pagina dedicata: tabella "DB locale vs Airtable" con scelta di quale versione mantenere |

**Chiave di deduplicazione Airtable:** `airtable_record_id` salvato nel DB locale. Alla creazione si usa `POST`, agli aggiornamenti `PATCH /<record_id>`.

---

## Autenticazione e Ruoli

### JWT
- Login con username + password → se 2FA abilitato, richiede codice TOTP prima di emettere il token
- JWT access token (8h) + refresh token
- Token inviato come Bearer header o httpOnly cookie
- Password hashata con bcrypt

### TOTP (Two-Factor Authentication)
- Libreria: `pyotp` (Python) — compatibile con Google Authenticator, Authy, qualsiasi app TOTP
- **Setup:** alla creazione utente (o dalla pagina profilo), l'Admin genera un QR code che il collega scansiona con la sua app authenticator
- **Login flow:** username + password → se TOTP abilitato → richiesta codice a 6 cifre → JWT emesso
- Il segreto TOTP è salvato cifrato nel DB (campo `totp_secret` in tabella `users`)
- Il campo `totp_enabled` (bool) permette all'Admin di abilitare/disabilitare il 2FA per utente
- Codici di backup: al setup vengono generati 8 codici monouso di emergenza (salvati hashati nel DB)

### Permessi per ruolo

| Funzionalità | Viewer | Editor | Admin |
|---|---|---|---|
| Vedere lista server | ✅ | ✅ | ✅ |
| Aggiungere server | ❌ | ✅ | ✅ |
| Modificare server | ❌ | ✅ | ✅ |
| Eliminare server | ❌ | ❌ | ✅ |
| Import da Airtable | ❌ | ❌ | ✅ |
| Export verso Airtable | ❌ | ✅ | ✅ |
| Gestire utenti | ❌ | ❌ | ✅ |
| Vedere audit log | ❌ | ❌ | ✅ |

### Pagina Gestione Utenti (solo Admin)
- Lista utenti con ruolo e stato attivo/disattivo
- Creazione utente con password temporanea
- Modifica ruolo e stato attivo
- Reset password
- Abilita/disabilita TOTP per utente + mostra QR code di setup
- Rigenera codici di backup di emergenza

---

## Duplicate Detection

**Livello 1 — Istantaneo (DB locale):** al `blur` del campo hostname, il frontend chiama `GET /api/servers/check-duplicate?hostname=<value>`. Risposta immediata dal DB locale.

**Livello 2 — Al submit (AWX API):** prima di creare l'host, il backend verifica via `GET /api/v2/hosts/?name=<hostname>` nell'inventory selezionato.

Se duplicato trovato: il submit viene bloccato e la UI mostra una card con i dati del server esistente (inventory, IP attuale, data inserimento, chi lo ha inserito).

---

## Struttura Progetto

```
ansible-inventory-ui/
├── frontend/                    # Next.js 14
│   ├── app/
│   │   ├── (auth)/login/        # Pagina login
│   │   ├── dashboard/           # Lista server + filtri
│   │   ├── servers/new/         # Wizard aggiunta server (4 step)
│   │   ├── servers/[id]/        # Dettaglio / modifica server
│   │   ├── admin/users/         # Gestione utenti (Admin)
│   │   ├── admin/audit/         # Audit log (Admin)
│   │   └── admin/airtable/      # Import/conflitti Airtable (Admin)
│   ├── components/
│   │   ├── ServerWizard/        # Step 1-4 wizard
│   │   ├── DuplicateAlert/      # Card avviso duplicato
│   │   └── UserTable/           # Tabella gestione utenti
│   ├── Dockerfile
│   └── package.json
│
├── backend/                     # FastAPI
│   ├── main.py
│   ├── config.py                # pydantic-settings
│   ├── database.py              # SQLAlchemy async
│   ├── models/
│   │   ├── server.py
│   │   ├── user.py
│   │   └── audit.py
│   ├── api/
│   │   ├── auth.py              # Login, JWT, refresh
│   │   ├── servers.py           # CRUD server + duplicate check
│   │   ├── users.py             # Gestione utenti (Admin)
│   │   └── airtable.py          # Import/export/conflitti
│   ├── integrations/
│   │   ├── awx_client.py        # AWX REST API v2
│   │   └── airtable_client.py   # Airtable REST API v0
│   ├── alembic/
│   ├── tests/
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── Dockerfile
│
├── docker-compose.yml
├── .env.example
├── .env                         # non committato
├── init.sh                      # crea primo utente Admin
└── nginx/
    ├── nginx.conf
    └── whitelist.conf
```

---

## Deployment

```yaml
# docker-compose.yml — struttura
services:
  db:      PostgreSQL 16
  backend: FastAPI (porta 8000)
  frontend: Next.js (porta 3000)
```

Nginx gira sull'host come reverse proxy con SSL Let's Encrypt (stesso schema InfraAI):
- `https://dominio/` → frontend (porta 3000)
- `https://dominio/api/` → backend (porta 8000)

**Primo avvio:** `./init.sh` crea l'utente Admin iniziale e applica le migration Alembic.

---

## Variabili d'Ambiente (`.env.example`)

```env
# Database
DATABASE_URL=postgresql+asyncpg://invui:invui@db:5432/invui

# AWX
AWX_URL=https://your-awx-server
AWX_TOKEN=your-awx-api-token

# Airtable
AIRTABLE_API_TOKEN=your-airtable-token
AIRTABLE_BASE_ID=your-base-id
AIRTABLE_TABLE_NAME=Servers

# Auth
JWT_SECRET=change-me-very-long-random-string
JWT_EXPIRE_HOURS=8

# Security (opzionale)
ALLOWED_IPS=1.2.3.4,5.6.7.8
```

---

## Fuori Scope (prima versione)

- SSO / OAuth (LDAP, Google, ecc.)
- Notifiche email/Telegram sulle modifiche
- Import massivo da CSV
- Dashboard grafici e statistiche
- Integrazione con InfraAI (i due progetti restano separati)
- Provisioning macchine (Terraform)
