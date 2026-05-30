# DBShield — Design Specification
**Data:** 2026-05-30  
**Versione:** 1.0  
**Autore:** Egidio Pescatore / EDM Informatica

---

## 1. Panoramica del prodotto

**DBShield** è una piattaforma web SaaS / on-premise per il backup automatico di database Microsoft SQL Server presenti su server Linux. Permette di schedulare, monitorare e gestire backup verso molteplici destinazioni di storage cloud e remoto, con un'interfaccia professionale, sistema di ruoli utente e cifratura end-to-end.

### Obiettivi principali
- Backup automatico di database MSSQL su server Linux verso destinazioni eterogenee
- Interfaccia web raggiungibile da remoto, user-friendly e graficamente accattivante
- Gerarchia di permessi utente (SuperAdmin → Admin → Operator → Viewer)
- Prodotto vendibile sia come SaaS che come licenza on-premise
- Installazione agente semplicissima (un comando copy-paste)

---

## 2. Architettura generale

### 2.1 Componenti

Il sistema è composto da due parti distinte:

#### Piattaforma centrale (Docker Compose)

| Servizio | Tecnologia | Ruolo |
|----------|-----------|-------|
| `api` | FastAPI (Python 3.11+) | REST API, autenticazione, logica business |
| `frontend` | React 18 + Vite + Tailwind CSS + shadcn/ui | SPA web |
| `db` | PostgreSQL 15 | Database applicativo |
| `redis` | Redis 7 | Code task, cache sessioni |
| `worker` | Celery | Esecuzione asincrona (polling agenti, notifiche) |
| `scheduler` | Celery Beat | Triggering job schedulati |
| `nginx` | Nginx | Reverse proxy, SSL termination |

#### Agente (server del cliente)

Processo Python leggero installato come **systemd service** (`dbshield-agent`) sul server Linux del cliente. Comunica con la piattaforma centrale via HTTPS polling (nessuna porta aperta in ingresso richiesta).

### 2.2 Flusso principale

```
Piattaforma (Celery Beat)
    ↓ job in scadenza
Worker → POST job pending su Redis

Agente (polling ogni 30s):
    GET /api/agent/jobs?token=XXX
    ← Lista job da eseguire

Per ogni job:
    1. Connessione MSSQL locale (pyodbc / sqlcmd)
    2. Dump database → file temporaneo locale
    3. Compressione gzip (opzionale)
    4. Cifratura AES-256-GCM (opzionale)
    5. Upload alla destinazione (S3 / SFTP / GDrive / OneDrive / Nextcloud / FTP)
    6. POST /api/agent/runs → report risultato (status, size, checksum)
    7. Pulizia file temporaneo locale

Piattaforma:
    → Aggiorna stato BackupRun
    → Invia notifiche (email / webhook)
    → Applica retention policy
```

### 2.3 Modalità di deployment

- **SaaS:** piattaforma gestita da EDM Informatica, clienti si registrano e collegano i propri server
- **On-premise:** cliente scarica il Docker Compose, installa sulla propria infrastruttura, attiva con licenza key

---

## 3. Modello dati

### Entità principali

#### Organization
| Campo | Tipo | Note |
|-------|------|------|
| id | UUID | PK |
| name | string | Nome organizzazione |
| plan | enum | saas_starter / saas_business / saas_enterprise / onpremise |
| license_key | string | Per versione on-premise |
| license_expires_at | datetime | Scadenza licenza |
| require_2fa | bool | Forza 2FA per tutti gli utenti dell'org |
| created_at | datetime | |

#### User
| Campo | Tipo | Note |
|-------|------|------|
| id | UUID | PK |
| org_id | UUID | FK Organization |
| email | string | Unique |
| password_hash | string | Bcrypt |
| role | enum | superadmin / admin / operator / viewer |
| two_fa_enabled | bool | |
| two_fa_secret | string (encrypted) | Seed TOTP cifrato AES-256 |
| two_fa_backup_codes | json (encrypted) | 8 codici monouso cifrati |
| is_active | bool | |
| last_login_at | datetime | |
| created_at | datetime | |

#### Server
| Campo | Tipo | Note |
|-------|------|------|
| id | UUID | PK |
| org_id | UUID | FK Organization |
| name | string | Nome friendly |
| hostname | string | |
| agent_token | string | Token Bearer univoco, revocabile |
| agent_version | string | Versione agente installata |
| last_seen_at | datetime | Ultimo polling ricevuto |
| status | enum | online / offline / never_connected |
| created_at | datetime | |

#### Database
| Campo | Tipo | Note |
|-------|------|------|
| id | UUID | PK |
| server_id | UUID | FK Server |
| name | string | Nome database MSSQL |
| mssql_instance | string | Istanza MSSQL (es. localhost\SQLEXPRESS) |
| credentials_encrypted | json (encrypted) | username, password cifrati |
| created_at | datetime | |

#### StorageDestination
| Campo | Tipo | Note |
|-------|------|------|
| id | UUID | PK |
| org_id | UUID | FK Organization |
| name | string | Nome friendly |
| type | enum | s3 / ftp / ftps / sftp / gdrive / onedrive / nextcloud / webdav |
| config_encrypted | json (encrypted) | Credenziali e parametri specifici per tipo |
| last_tested_at | datetime | Ultimo test connessione |
| last_test_ok | bool | Esito ultimo test |
| created_at | datetime | |

#### BackupJob
| Campo | Tipo | Note |
|-------|------|------|
| id | UUID | PK |
| org_id | UUID | FK Organization |
| name | string | Nome friendly |
| database_ids | json | Lista UUID database (multi-database) |
| destination_id | UUID | FK StorageDestination |
| schedule_cron | string | Espressione cron (es. "0 2 * * 1") |
| compression_enabled | bool | Compressione gzip |
| encryption_enabled | bool | Cifratura AES-256 |
| encryption_password | string (encrypted) | Password cifratura cifrata |
| retention_days | int | Giorni conservazione (0 = illimitato) |
| enabled | bool | |
| created_at | datetime | |

#### BackupRun
| Campo | Tipo | Note |
|-------|------|------|
| id | UUID | PK |
| job_id | UUID | FK BackupJob |
| started_at | datetime | |
| finished_at | datetime | |
| status | enum | pending / running / success / failed / cancelled |
| size_bytes | bigint | Dimensione file backup |
| file_path | string | Path nel destinazione storage |
| checksum_sha256 | string | Checksum file |
| error_message | text | Messaggio di errore se fallito |
| triggered_by | enum | scheduler / manual / api |
| triggered_by_user_id | UUID | FK User (se manuale) |

#### NotificationChannel
| Campo | Tipo | Note |
|-------|------|------|
| id | UUID | PK |
| org_id | UUID | FK Organization |
| name | string | Nome friendly |
| type | enum | email / webhook |
| config | json | Per email: {to, smtp_...}; per webhook: {url, secret} |
| on_success | bool | Notifica su successo |
| on_failure | bool | Notifica su fallimento |
| enabled | bool | |

#### AuditLog
| Campo | Tipo | Note |
|-------|------|------|
| id | UUID | PK |
| org_id | UUID | FK Organization |
| user_id | UUID | FK User (nullable per azioni agente) |
| action | string | Es. "backup_job.created", "user.login", "storage.tested" |
| target_type | string | Tipo entità coinvolta |
| target_id | UUID | ID entità coinvolta |
| metadata | json | Dati aggiuntivi contestuali |
| ip_address | string | |
| user_agent | string | |
| created_at | datetime | |

---

## 4. Interfaccia utente

### Layout generale
- Sidebar sinistra fissa con navigazione principale
- Area contenuto principale
- Header con nome utente, organizzazione, notifiche, toggle dark/light mode
- Design: Tailwind CSS + shadcn/ui, palette neutra con accenti blu (primario), verde (successo), rosso (errore), arancione (warning)
- Completamente responsive (desktop-first, usabile anche da tablet)

### Pagine

#### Autenticazione
- `/login` — email + password + campo 2FA (se abilitato)
- `/2fa/setup` — QR code + verifica codice TOTP + download backup codes
- `/password-reset` — richiesta reset via email
- `/password-reset/:token` — impostazione nuova password

#### Dashboard (`/`)
- Widget: server online/offline, job attivi, backup nelle ultime 24h, storage utilizzato
- Grafico a barre: backup riusciti vs falliti ultimi 30 giorni
- Lista alert attivi: job in errore, agenti offline, licenza in scadenza

#### Server & Agenti (`/servers`)
- Tabella server con: nome, hostname, status (badge colorato), last seen, n° database, n° job
- Dettaglio server: tab Database, tab Job associati, tab Log recenti
- Modale "Aggiungi server": genera token e mostra comando di installazione agente (copy-paste)
- Pulsante "Revoca token" con conferma

#### Job di Backup (`/jobs`)
- Tabella job: nome, database, destinazione, prossima esecuzione, stato ultima run
- Wizard creazione job (5 step):
  1. Selezione database (uno o più)
  2. Selezione destinazione storage
  3. Schedulazione (selettore visuale o modalità cron avanzata)
  4. Opzioni (compressione, cifratura, retention)
  5. Notifiche (canali da associare)
- Dettaglio job: storico esecuzioni, log, pulsante "Esegui ora", pulsante download backup

#### Destinazioni Storage (`/storage`)
- Lista destinazioni con tipo (icona), nome, stato connessione, ultima verifica
- Form configurazione per tipo (campi specifici per S3, SFTP, GDrive, ecc.)
- Pulsante "Testa connessione" con feedback immediato

#### Log & Audit (`/logs`)
- Tab "Esecuzioni backup": filtri per server/job/stato/data, colonna status colorata, link dettaglio
- Tab "Audit trail": azioni utenti con IP e timestamp (solo Admin/SuperAdmin)

#### Utenti & Organizzazioni (`/users`) — Admin/SuperAdmin
- Lista utenti con ruolo, stato 2FA, ultima attività
- Invito utente via email
- Modifica ruolo, disattivazione account
- Gestione organizzazioni (solo SuperAdmin)

#### Impostazioni (`/settings`)
- Profilo: nome, email, cambio password
- Sicurezza: setup/rimozione 2FA, sessioni attive
- Organizzazione: SMTP per notifiche email, logo (white-label), require_2fa globale
- Licenza: piano attivo, scadenza, upgrade

---

## 5. Agente

### Installazione
```bash
curl -sSL https://app.dbshield.io/install.sh | bash -s -- --token=AGENT_TOKEN
```
Lo script:
1. Rileva la distribuzione Linux
2. Installa Python 3.9+ se non presente
3. Installa le dipendenze Python (`dbshield-agent` package)
4. Crea il file di configurazione `/etc/dbshield-agent/config.json`
5. Registra e avvia il servizio systemd `dbshield-agent`
6. Verifica la connessione alla piattaforma

### Configurazione agente
```json
{
  "api_url": "https://app.dbshield.io",
  "agent_token": "tok_xxxxx",
  "poll_interval_seconds": 30,
  "log_level": "INFO",
  "temp_dir": "/tmp/dbshield"
}
```

### Sicurezza agente
- Token univoco per agente, revocabile dalla dashboard
- Credenziali MSSQL e storage non persistite sul server del cliente — ricevute cifrate per ogni job ed usate solo in memoria
- File temporanei eliminati immediatamente dopo l'upload
- Log locale in `/var/log/dbshield-agent/`
- Comunicazione esclusivamente HTTPS uscente (porta 443)

### Requisiti minimi server cliente
- OS: Ubuntu 20.04+, Debian 11+, RHEL/CentOS 8+
- Python 3.9+
- SQL Server accessibile localmente o in rete LAN
- Connessione HTTPS uscente porta 443

---

## 6. Sicurezza

| Area | Implementazione |
|------|----------------|
| Autenticazione | JWT access token (15 min) + refresh token (30 giorni) in httpOnly cookie |
| 2FA | TOTP RFC 6238 (pyotp), backup codes monouso, forzabile per organizzazione |
| Cifratura a riposo | AES-256-GCM per credenziali DB, config storage, secret 2FA (chiave da env var) |
| Password | Bcrypt con cost factor 12, policy minima configurabile (lunghezza, complessità) |
| Rate limiting | Login: 5 tentativi poi lockout 15 min; API: rate limit per IP e per token |
| HTTPS | TLS 1.2+, HSTS, certificato Let's Encrypt automatico via Certbot |
| CORS | Whitelist domini esplicita |
| Audit log | Ogni azione sensibile tracciata con IP, user-agent, timestamp |
| Token agente | Bearer token univoco, revocabile istantaneamente dalla dashboard |
| Input validation | Pydantic su tutti gli endpoint API, sanitizzazione input |
| SQL injection | Solo ORM (SQLAlchemy), nessuna query raw |

---

## 7. Destinazioni storage supportate (v1.0)

| Tipo | Libreria Python | Note |
|------|----------------|------|
| Amazon S3 / compatibili (MinIO, Wasabi, Backblaze B2) | `boto3` | Endpoint configurabile |
| FTP / FTPS | `ftplib` stdlib | Supporto TLS esplicito/implicito |
| SFTP / SSH | `paramiko` | Autenticazione password o chiave SSH |
| Google Drive | `google-auth` + Drive API v3 | OAuth2, token refresh automatico |
| OneDrive | `msal` + Graph API | OAuth2 |
| Nextcloud / WebDAV | `webdavclient3` | Compatibile con qualsiasi server WebDAV |

---

## 8. Notifiche

### Email (SMTP)
- Configurazione SMTP per organizzazione (host, porta, TLS, credenziali)
- Template HTML professionale con logo organizzazione
- Eventi: backup completato, backup fallito, agente offline, licenza in scadenza

### Webhook
- POST JSON su URL configurato
- Header `X-DBShield-Signature` con HMAC-SHA256 per verifica autenticità
- Payload standard compatibile con Slack Incoming Webhooks, Teams, n8n, Zapier
- Retry automatico (3 tentativi con backoff esponenziale) in caso di errore

---

## 9. Licenze e piani

### SaaS (gestito da EDM Informatica)

| Piano | Server | Job | Prezzo indicativo |
|-------|--------|-----|------------------|
| Starter | 2 | 5 | €29/mese |
| Business | 10 | 50 | €99/mese |
| Enterprise | Illimitato | Illimitato | €299/mese |

### On-premise (self-hosted dal cliente)

| Tier | Server | Prezzo indicativo |
|------|--------|------------------|
| Small | 5 | €299/anno |
| Business | 25 | €799/anno |
| Enterprise | Illimitato | €1.999/anno |

- Verifica licenza all'avvio della piattaforma
- Funzionamento offline garantito per 30 giorni dopo scadenza
- Aggiornamenti inclusi per 1 anno

### White-label
- Logo, nome prodotto e colori primari personalizzabili
- Dominio custom supportato
- Disponibile per piani Business/Enterprise

---

## 10. Roadmap (v1.x)

| Feature | Priorità | Note |
|---------|---------|------|
| Verifica integrità backup (checksum SHA256 post-upload) | Alta | |
| Notifiche Telegram e Slack native | Media | |
| Report settimanale/mensile via email | Media | |
| API pubblica documentata (OpenAPI) | Media | |
| Pannello multi-tenant reseller | Media | |
| Supporto MySQL e PostgreSQL | Alta | |
| Backup differenziale | Bassa | |
| Mobile app (iOS/Android) | Bassa | |

---

## 11. Stack tecnologico riepilogativo

| Layer | Tecnologia |
|-------|-----------|
| Backend API | Python 3.11, FastAPI, SQLAlchemy, Alembic, Pydantic |
| Task queue | Celery + Redis |
| Database | PostgreSQL 15 |
| Frontend | React 18, Vite, TypeScript, Tailwind CSS, shadcn/ui, React Query, React Router |
| Autenticazione | JWT (python-jose), bcrypt, pyotp (TOTP) |
| Cifratura | cryptography (AES-256-GCM) |
| Agente | Python 3.9+, pyodbc, boto3, paramiko, google-auth, msal, webdavclient3 |
| Infrastruttura | Docker, Docker Compose, Nginx, Certbot |
| CI/CD | GitHub Actions (build, test, push image) |
