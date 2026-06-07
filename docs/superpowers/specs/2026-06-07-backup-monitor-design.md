# Design: Backup Monitor — Sistema di Backup Centralizzato per 100 VPS TeamSystem

**Data:** 2026-06-07  
**Stato:** Approvato

---

## Contesto e Problema

~100 VPS Ubuntu (22.04 / 24.04) con software **TeamSystem** basato su **AcuCOBOL** (file dati in formato Vision/ISAM). I file Vision vengono bloccati durante l'utilizzo del gestionale, rendendo i backup live (rsync) potenzialmente corrotti.

Problemi attuali:
- Backup live con rsync → rischio corruzione file Vision
- Storage FreeNAS in esaurimento (nessuna deduplicazione)
- Notifiche via email per ogni server → impossibile gestire 100 notifiche
- Nessuna verifica che i backup siano effettivamente ripristinabili
- Nessuna visibilità centralizzata sullo stato dei backup

---

## Architettura

### Componenti

```
100 VPS Ubuntu
    │  cron 02:00 → stop TeamSystem → restic backup → start TeamSystem → POST status
    │  cron 03:30 → restic restore test → verifica checksum → POST esito
    │
    ▼  S3 API (SFTP-compatibile)
Contabo Object Storage (S3)
    │  1 bucket per VPS: s3://backup/vps-001/, s3://backup/vps-002/, ...
    │  Deduplicazione chunk-level (restic) + compressione zstd
    │  Retention: --keep-daily 7 --keep-weekly 4
    │
    ▼  HTTP POST (JSON)
Master Service (1 VPS Contabo dedicata ~€4/mese)
    │  FastAPI (Python) + SQLite
    │  Dashboard web :8080
    │  Alert engine
    │
    ▼
Notifiche (Telegram + Email + WhatsApp)
```

### Flusso Backup (ogni VPS, 02:00)

1. `systemctl stop teamsystem`
2. `restic backup /home/Nativo* /home/GecomNativo* --json`  
   *(path configurabili per server)*
3. `systemctl start teamsystem`  
   *(downtime stimato: 1-3 minuti)*
4. POST a Master API: `{ vps_id, status, size_gb, duration_s, snapshot_id, folders, timestamp }`

### Flusso Restore Test (ogni VPS, 03:30)

1. Recupera snapshot_id dell'ultimo backup dalla Master API
2. `restic restore <snapshot_id> --target /tmp/restore-test --include <file-campione>`  
   *(file campione = file più recentemente modificato nella prima cartella backuppata)*
3. Verifica checksum SHA256 del file ripristinato vs. originale sul filesystem live
4. Elimina `/tmp/restore-test`
5. POST a Master API: `{ vps_id, restore_status, checksum_ok, duration_s, timestamp }`

### Master Service

- **Stack:** Python 3.12, FastAPI, SQLite, Jinja2 (template HTML)
- **Endpoint REST:**
  - `POST /api/v1/backup/report` — riceve status backup da VPS
  - `POST /api/v1/restore/report` — riceve esito restore test da VPS
  - `GET /api/v1/servers` — lista server con ultimo stato
  - `GET /api/v1/servers/{vps_id}` — dettaglio + storico
  - `GET /api/v1/servers/{vps_id}/snapshots/{snapshot_id}/download` — stream tar.gz
  - `GET /api/v1/servers/{vps_id}/snapshots/{snapshot_id}/download/{folder}` — stream cartella specifica
- **Alert engine:** controlla ogni ora se un VPS non ha fatto backup da >25h, restore test fallito, errori ripetuti
- **Download:** `restic dump <snapshot_id> <path>` in streaming diretto al browser; per archivi >5 GB genera link temporaneo (JWT, validità 24h) e notifica

---

## Dashboard Web

### Vista Principale (tabella)

Colonne: Server | Cliente | OS | Stato | Orario | Ultimo Backup | Cartelle | Dim. Backup | Disco VPS | Restore Test | →

- **Stato:** ✅ OK / ❌ FAILED / ⚠️ STALE (nessun backup da >25h)
- **OS:** badge colorato dinamico per distro (`Ubuntu 22.04` blu, `Ubuntu 24.04` verde, `Debian` viola, `CentOS` rosso, altri assegnati automaticamente, `Unknown OS` grigio come fallback)
- **Disco VPS:** barra colorata — verde >40% libero, giallo 20-40%, rosso <20%
- **Filtri:** per stato, per OS, ricerca testuale

### Vista Dettaglio (singolo server)

- 5 KPI: ultimo backup, dimensione, durata, disco libero, restore test
- Cartelle backuppate con pulsante download `.tar.gz` (ultimo snapshot)
- Storico 7 giorni: stato, dimensione, durata, downtime, restore, download, log
- Download per snapshot storico: "⬇ Tutto" o "Cartella…" (selettore cartella)
- Pulsanti: Modifica config, Restore manuale

---

## Notifiche

Tre canali, configurabili per soglia:

| Canale | Tool | Quando |
|--------|------|--------|
| **Telegram** | Bot API (gratuito) | Alert istantaneo su FAILED, STALE, restore fallito |
| **Email** | SMTP / SendGrid | Digest giornaliero riepilogativo + alert critici |
| **WhatsApp** | Callmebot (gratuito) o Twilio (a pagamento, più affidabile) | Alert critici (es. >3 server falliti contemporaneamente) |

Messaggio tipo Telegram:
```
🔴 BACKUP FALLITO
Server: vps-017 (Ferrari SpA)
Data: 2026-06-07 02:03
Errore: connection timeout S3
→ http://master:8080/servers/vps-017
```

---

## Storage S3 (Contabo)

- **1 bucket per VPS** — isolamento e permessi separati
- **Credenziali:** ogni VPS ha access key/secret key dedicati (principio di least privilege)
- **Retention restic:**
  ```
  restic forget --keep-daily 7 --keep-weekly 4 --prune
  ```
  Eseguito dopo ogni backup riuscito
- **Stima spazio:** con deduplicazione restic su file Vision, atteso risparmio del 60-70% rispetto a rsync. Con retention 7 giorni il consumo totale sarà indicativamente inferiore all'attuale configurazione rsync a 2 giorni

---

## Deploy con Ansible

Un playbook unico copre tutte le 100 VPS:

1. Installa `restic` (binary scaricato da GitHub releases)
2. Scrive `/etc/restic/vps-XXX.env` con credenziali S3 e password repository
3. Scrive `/usr/local/bin/backup-teamsystem.sh` (script backup)
4. Scrive `/usr/local/bin/restore-test-teamsystem.sh` (script restore test)
5. Crea cron job `02:00` e `03:30`
6. Esegue `restic init` sul repository S3
7. Registra il VPS sul Master Service (`POST /api/v1/servers/register`)

Variabili per server: hostname, IP, cartelle da backuppare, orario personalizzato, credenziali S3.

---

## Autenticazione Dashboard

La dashboard richiede autenticazione a prescindere dalla rete su cui è esposta.

### Metodi di accesso supportati

**1. Username + Password + TOTP (2FA)**
- Password hashata con bcrypt (cost factor 12)
- 2FA obbligatorio tramite TOTP (RFC 6238) — compatibile con Google Authenticator, Authy, 1Password, ecc.
- Setup 2FA al primo accesso: QR code generato lato server, mai trasmesso in chiaro
- Codici di recupero monouso (10 codici) generati al setup 2FA, mostrati una sola volta

**2. Passkey (WebAuthn / FIDO2)**
- Accesso passwordless tramite impronta digitale, Face ID, chiave hardware (YubiKey, ecc.)
- Implementazione: libreria `py_webauthn` sul backend FastAPI
- Registrazione passkey disponibile dal pannello profilo dopo il primo accesso con password
- Possibilità di registrare più passkey per lo stesso account (es. laptop + telefono)

### Flusso di accesso

```
Login page
    ├── [Accedi con Passkey]  → challenge WebAuthn → dashboard
    └── [Username + Password]
            └── credenziali OK → richiesta codice TOTP → dashboard
```

### Sessioni

- Sessione autenticata: cookie httpOnly + SameSite=Strict, durata 8 ore
- Rinnovo silenzioso se attivo nelle ultime 2 ore
- Logout esplicito invalida il cookie lato server (blocklist in SQLite)

### Gestione utenti

- Tabella `users` in SQLite: id, username, password_hash, totp_secret (cifrato), passkey_credentials (JSON)
- Nessun sistema di registrazione pubblica — gli utenti sono creati via CLI sul Master Service:  
  `python manage.py create-user --username admin`
- Supporto multi-utente (es. amministratore + tecnico in sola lettura)

---

## Sicurezza

- Link di download temporanei firmati con JWT (validità 24h)
- Credenziali S3 per VPS mai in chiaro nei log
- Repository restic cifrati con password (AES-256)
- Comunicazione Master ↔ VPS via HTTPS (certificato self-signed o Let's Encrypt)
- Rate limiting sul login: blocco temporaneo dopo 5 tentativi falliti in 10 minuti
- Header di sicurezza HTTP: `Strict-Transport-Security`, `X-Frame-Options`, `Content-Security-Policy`

---

## Componenti da Costruire

| Componente | Tecnologia | Note |
|-----------|-----------|------|
| Script bash backup | Bash | 1 file, parametrizzato |
| Script bash restore test | Bash | 1 file, parametrizzato |
| Playbook Ansible deploy | Ansible | 1 playbook, inventory dinamico |
| Master Service API | Python / FastAPI | ~500 righe |
| Dashboard web | HTML/CSS/JS (Jinja2) | Server-side rendering, no framework JS |
| Alert engine | Python (integrato nel Master) | Modulo separato |
| DB schema | SQLite | 5 tabelle: servers, backup_runs, restore_runs, users, sessions |
| Auth / WebAuthn | py_webauthn + PyOTP | Passkey + TOTP 2FA |

---

## Non in Scope

- Interfaccia per configurare le notifiche (configurazione via file YAML sul Master)
- Multi-tenancy / accesso per cliente finale
- Backup di database (solo filesystem Vision)
- Backup incrementali intra-giornalieri (solo 1 backup/giorno alle 02:00)
