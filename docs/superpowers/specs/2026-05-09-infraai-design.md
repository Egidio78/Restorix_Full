# InfraAI — Design Specification
**Date:** 2026-05-09
**Author:** EDM Informatica — Sistemista

---

## Contesto

Sistema di gestione infrastrutturale guidato da AI per un parco di circa 400 macchine miste (Linux/Windows, cloud e fisiche) distribuite su provider Hetzner, Contabo, VH e hardware fisico. Il sistema permette di governare l'intera infrastruttura tramite linguaggio naturale in italiano, attraverso una chat web e alert su Telegram.

---

## Obiettivi

- Eseguire operazioni di manutenzione (aggiornamenti, restart servizi, lettura log) tramite chat in linguaggio naturale
- Monitorare lo stato del parco macchine con alert proattivi su Telegram
- Gestire upgrade di versione OS (es. Ubuntu 22.04 → 24.04) su richiesta esplicita
- Mantenere un inventario unificato di tutte le macchine
- Architettura monoutente oggi, pronta per scalare a team in futuro

---

## Architettura

### Approccio scelto
**VPS dedicata "AI Brain"** su Hetzner CX21 (2 vCPU, 4GB RAM, ~6€/mese). Lo stack esistente (Ansible x2, Zabbix, Uptime Kuma, Remote Desktop Manager) rimane invariato.

### Componenti

```
┌─────────────────────────────────────────────────────┐
│                  VPS AI Brain (nuova)                │
│                                                      │
│  ┌─────────────┐    ┌──────────────┐                │
│  │  Chat Web   │    │  Backend AI  │                │
│  │  (Next.js)  │◄──►│  (FastAPI +  │                │
│  └─────────────┘    │   Claude)    │                │
│                     └──────┬───────┘                │
│                            │                        │
│              ┌─────────────┼──────────────┐         │
│              ▼             ▼              ▼         │
│       ┌─────────┐  ┌────────────┐  ┌──────────┐   │
│       │Ansible  │  │  Zabbix    │  │  Uptime  │   │
│       │ Router  │  │  API       │  │  Kuma API│   │
│       └────┬────┘  └────────────┘  └──────────┘   │
│            │                                        │
│     ┌──────┴──────┐                                │
│     ▼             ▼                                │
│  Ansible      Ansible                              │
│  Stable       New                                  │
│  (≤22.04)     (≥24.04)                             │
└─────────────────────────────────────────────────────┘
         │                          │
         ▼                          ▼
    Telegram Bot              400 Servers
    (alert + comandi)
```

| Componente | Tecnologia | Ruolo |
|---|---|---|
| Chat Web | Next.js (React) | Interfaccia principale, streaming risposte |
| Backend AI | Python + FastAPI | Motore centrale, integra Claude API |
| Claude | claude-sonnet-4-6 | Comprensione linguaggio naturale, ragionamento |
| Ansible Router | ansible-runner (Python) | Smista task al controller corretto in base all'OS |
| Ansible Stable | Esistente | Gestisce macchine con Ubuntu ≤22.04 |
| Ansible New | Esistente | Gestisce macchine con Ubuntu ≥24.04 |
| Zabbix API | REST/JSON-RPC | Inventario e monitoring Windows |
| Uptime Kuma API | REST | Monitoring servizi web e certificati SSL |
| Telegram Bot | python-telegram-bot | Alert proattivi e comandi rapidi |
| Database | PostgreSQL | Inventario unificato, audit log, storico comandi |

---

## Flusso di una Richiesta

```
Utente scrive: "Aggiorna tutti i server Ubuntu 24.04 del cliente Rossi"
         │
         ▼
   Backend AI (Claude)
   ├─ Parsing intento: UPDATE + filtro cliente + filtro OS
   ├─ Query DB inventario → lista host del cliente "Rossi"
   ├─ Per ogni host → legge versione OS dal DB
   ├─ Routing: Ubuntu ≤22.04 → Ansible Stable
   │            Ubuntu ≥24.04 → Ansible New
   ├─ Esecuzione playbook apt upgrade in parallelo
   ├─ Raccolta output strutturato per ogni macchina
   └─ Risposta in chat: "✅ 12 aggiornati, ⚠️ 2 con errori su..."
         │
         ▼
   Se errori critici → alert Telegram automatico
```

---

## Regole di Autonomia

| Operazione | Comportamento |
|---|---|
| Leggere log / stato servizi | Esegue senza chiedere |
| Aggiornamenti pacchetti (apt upgrade) | Esegue senza chiedere |
| Riavviare un servizio | Esegue senza chiedere |
| Generare report | Esegue senza chiedere |
| Upgrade OS (es. 22.04 → 24.04) | Solo su richiesta esplicita utente. Mostra piano (macchine, ordine, tempi) prima di procedere. Mai in automatico. |
| Aggiungere/rimuovere utenti | Chiede conferma esplicita |
| Modifiche firewall/rete | Chiede conferma esplicita |

Le soglie di autonomia sono configurabili via file senza modificare il codice. L'architettura è pronta per gestire ruoli differenziati quando si aggiunge un team.

---

## Monitoring e Alert Telegram

### Severity e Canali

| Livello | Trigger | Notifica |
|---|---|---|
| CRITICAL 🔴 | Server down, disco >95%, DB giù, SSL scaduto | Immediato |
| WARNING 🟡 | CPU >85% per 10min, RAM >90%, disco >80%, SSL scade <7gg | Entro 5 minuti |
| INFO 🔵 | Report giornaliero salute infrastruttura, aggiornamenti disponibili | Ogni mattina ore 08:00 |

### Funzionalità Telegram Bot
- Alert con dettaglio: hostname, metrica, valore attuale
- Risposta diretta al bot per comandi rapidi (es. `riavvia nginx su srv-01`)
- Silenziamento per manutenzione: `/silence srv-01 2h`
- Report giornaliero alle 08:00

Tutte le soglie sono configurabili via file senza toccare il codice.

---

## Inventario Macchine

### Fonti dati

| Fonte | Copertura | Modalità |
|---|---|---|
| Zabbix API | Server Windows | Sync automatica ogni ora |
| RDM CSV export | Server Linux | Import manuale tramite UI (o schedulato) |
| Uptime Kuma API | Servizi web | Sync automatica per stato uptime |
| File YAML arricchito | Tutti | Cliente, ruolo, note critiche, override controller |

### Struttura file YAML arricchito
```yaml
servers:
  - hostname: srv-web-01
    cliente: Rossi Srl
    ruolo: webserver
    note: "macchina critica, avvisare sempre prima di toccare"
    ansible_controller: auto   # auto | stable | new
```

Il database InfraAI unifica tutte le fonti. La chat web include una pagina di import CSV per aggiornare l'inventario Linux da RDM.

### Routing Ansible automatico

L'Ansible Router legge la versione OS dal database per ogni host target:
- Ubuntu ≤22.04 → Ansible Stable
- Ubuntu ≥24.04 → Ansible New
- Altre distro Linux (Debian, CentOS, AlmaLinux, ecc.) → Ansible Stable per default, override via YAML
- Override manuale possibile via campo `ansible_controller` nel YAML

Dopo ogni upgrade OS, la versione nel DB viene aggiornata automaticamente e il routing cambia di conseguenza.

---

## Stack Tecnologico

| Layer | Tecnologia |
|---|---|
| Backend AI | Python 3.12 + FastAPI |
| AI Model | Claude (claude-sonnet-4-6) via Anthropic API |
| Frontend | Next.js 14 (React) |
| Ansible integration | ansible-runner (Python) |
| Telegram | python-telegram-bot |
| Database | PostgreSQL 16 |
| Container | Docker Compose |
| Web server / proxy | Nginx |
| SSL | Let's Encrypt (Certbot) |

---

## Sicurezza

- HTTPS obbligatorio con certificato Let's Encrypt
- **Whitelist IP**: la chat web risponde solo agli IP autorizzati (configurabili in nginx senza riavvio app)
- Autenticazione con password anche per IP in whitelist (doppio livello)
- Chiavi SSH Ansible in volume Docker cifrato
- API keys (Anthropic, Zabbix, Kuma, Telegram) in file `.env` non committato
- Accesso SSH alla VPS AI Brain limitato agli IP del sistemista
- Quando si aggiunge un team: ogni utente ha IP autorizzato + credenziali proprie

---

## Deployment

```
VPS Hetzner CX21
└── docker-compose.yml
    ├── infra-ai-backend    (FastAPI + Claude)
    ├── infra-ai-frontend   (Next.js)
    ├── infra-ai-db         (PostgreSQL)
    └── infra-ai-telegram   (Telegram bot worker)
```

Nginx gira sull'host (fuori Docker) come reverse proxy con whitelist IP e terminazione SSL.

---

## Fuori Scope (prima versione)

- Gestione multi-tenant / multi-cliente con accesso separato per cliente
- Dashboard grafici avanzati (Grafana)
- Provisioning nuove macchine (Terraform)
- Autenticazione 2FA (prevista in futuro)
- Gestione Windows tramite WinRM/PowerShell (prevista in futuro)
