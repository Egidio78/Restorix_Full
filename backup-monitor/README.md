# Backup Monitor

Sistema centralizzato per il monitoraggio dei backup su più VPS.

## Quick Start

```bash
git clone <repo> backup-monitor
cd backup-monitor

# Configura le variabili d'ambiente
cp master/.env.example master/.env
# Modifica master/.env con i tuoi valori (MASTER_SECRET, JWT_SECRET, ecc.)

# Avvia
docker compose up -d
```

Il master sarà disponibile su `http://localhost:8080`.

## Primo utente admin

```bash
docker compose exec master python manage.py create-user --username admin
```

Segui le istruzioni per impostare la password e abilitare il TOTP.

## Registrare un VPS

Ottieni prima un token agent dal pannello admin, poi sul VPS:

```bash
curl -X POST https://backup-monitor.tuodominio.com/api/v1/servers/register \
  -H "Content-Type: application/json" \
  -d '{
    "hostname": "vps-01.example.com",
    "agent_token": "il-tuo-agent-token"
  }'
```

## Struttura del progetto

```
backup-monitor/
├── master/               # Servizio FastAPI centrale
│   ├── main.py
│   ├── models.py
│   ├── auth.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── docker-compose.yml
├── data/                 # Volume persistente SQLite (creato automaticamente)
└── README.md
```

## Deploy con Ansible

```bash
ansible-playbook -i inventory.yml playbook.yml
```

Assicurati che `inventory.yml` contenga l'host target e che le variabili
`master_secret`, `jwt_secret` e `totp_encryption_key` siano definite
(es. in `group_vars/all/vault.yml` cifrato con ansible-vault).
