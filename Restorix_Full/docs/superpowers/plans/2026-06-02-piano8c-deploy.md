# Piano 8c — Deploy su Server Produzione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deployare Restorix v1.4.0 sul server `egidio@46.225.106.181` con nginx + SSL Let's Encrypt per `restorix.edminformatica.it`.

**Architecture:** Stack Docker Compose su `/opt/restorix/` con network dedicato `restorix_default`. Container nginx dedicato su porte 80/443, SSL via certbot. Isolato dagli altri progetti sul server (OpenHuman su porta 7788).

**Tech Stack:** Docker Compose / nginx / Let's Encrypt certbot / PostgreSQL 15 / Redis 7

**Prerequisiti:**
- Piano 8a e 8b completati e pushati su GitHub
- DNS `restorix.edminformatica.it` → `46.225.106.181` configurato e propagato
- SSH: `ssh -i ~/.ssh/codex_awx egidio@46.225.106.181`

---

### Task 1: Setup directory e clone repo sul server

- [ ] **Step 1: Connettiti al server e crea la directory**

```bash
ssh -i ~/.ssh/codex_awx egidio@46.225.106.181
sudo mkdir -p /opt/restorix
sudo chown egidio:egidio /opt/restorix
```

- [ ] **Step 2: Clona il repo**

```bash
cd /opt/restorix
git clone https://github.com/Egidio78/Restorix_Full.git .
```

- [ ] **Step 3: Verifica struttura**

```bash
ls /opt/restorix/
```

Output atteso: `agent/  backend/  docker-compose.yml  docs/  frontend/  Makefile  nginx/`

---

### Task 2: Configura il file .env

- [ ] **Step 1: Crea il .env da template**

```bash
cd /opt/restorix
cp .env.example .env 2>/dev/null || touch .env
```

- [ ] **Step 2: Imposta le variabili**

```bash
cat > /opt/restorix/.env << 'EOF'
# App
APP_ENV=production
APP_NAME=Restorix
SECRET_KEY=<genera con: openssl rand -hex 32>
CORS_ORIGINS=https://restorix.edminformatica.it

# Database
DATABASE_URL=postgresql+asyncpg://restorix:restorix_pass@db:5432/restorix
POSTGRES_DB=restorix
POSTGRES_USER=restorix
POSTGRES_PASSWORD=<genera con: openssl rand -hex 16>

# Redis
REDIS_URL=redis://:redis_pass@redis:6379/0
REDIS_PASSWORD=<genera con: openssl rand -hex 16>

# Email SMTP (per notifiche)
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=noreply@edminformatica.it

# Retention
RETENTION_ENABLED=true

# Restore temp dir
RESTORE_TEMP_HOST_PATH=/opt/restorix/restore-tmp
EOF
```

Sostituisci i valori `<genera con: ...>` con valori reali:
```bash
openssl rand -hex 32   # per SECRET_KEY
openssl rand -hex 16   # per POSTGRES_PASSWORD e REDIS_PASSWORD
```

- [ ] **Step 3: Crea directory restore-tmp**

```bash
mkdir -p /opt/restorix/restore-tmp
chmod 755 /opt/restorix/restore-tmp
```

---

### Task 3: Configura docker-compose.yml per produzione

- [ ] **Step 1: Verifica che docker-compose.yml usi variabili da .env**

```bash
grep -n "POSTGRES_PASSWORD\|REDIS_PASSWORD\|SECRET_KEY" /opt/restorix/docker-compose.yml | head -10
```

Se il file usa valori hard-coded invece di variabili d'ambiente, aggiornali per usare `${VARIABILE}`.

- [ ] **Step 2: Verifica che il network sia dedicato**

```bash
grep -n "networks\|restorix" /opt/restorix/docker-compose.yml | head -10
```

Il compose deve definire un network `restorix_default` (o il default auto-generato). Non deve condividere `openhuman_default`.

- [ ] **Step 3: Aggiungi nginx al docker-compose (se non presente)**

Se il `docker-compose.yml` copiato da Backup_Machine non include il container nginx per la prod, aggiungilo:

```yaml
  nginx:
    image: nginx:alpine
    container_name: restorix-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - /etc/letsencrypt:/etc/letsencrypt:ro
      - ./frontend/dist:/usr/share/nginx/html:ro
      - ./agent/install.sh:/usr/share/nginx/html/install.sh:ro
      - ./agent/dist:/usr/share/nginx/html/agent:ro
    depends_on:
      - api
```

---

### Task 4: Build e avvio stack Docker

- [ ] **Step 1: Build delle immagini**

```bash
cd /opt/restorix
docker compose build
```

Questo può richiedere 5-10 minuti per il frontend.

- [ ] **Step 2: Avvio stack**

```bash
docker compose up -d
```

- [ ] **Step 3: Verifica container attivi**

```bash
docker compose ps
```

Output atteso: tutti i servizi `Up` o `healthy`:
```
restorix-api       Up (healthy)
restorix-worker    Up
restorix-scheduler Up
restorix-db        Up (healthy)
restorix-redis     Up (healthy)
restorix-frontend  Up
```

- [ ] **Step 4: Applica migration Alembic**

```bash
docker compose exec api alembic upgrade head
```

Output atteso: `Running upgrade ... -> 0011, mysql_support`

- [ ] **Step 5: Crea utente admin**

```bash
docker compose exec api python scripts/create_admin.py \
  --email egidio.pescatore@edminformatica.com \
  --password "CambiamiSubito!"
```

- [ ] **Step 6: Verifica API health**

```bash
curl -s http://localhost:8000/api/health
```

Output atteso: `{"status":"ok","app":"Restorix"}`

---

### Task 5: Nginx + SSL Let's Encrypt

- [ ] **Step 1: Verifica che DNS sia propagato**

```bash
dig restorix.edminformatica.it +short
```

Output atteso: `46.225.106.181`

Se il DNS non è ancora propagato, attendi e riprova (può richiedere fino a 24h, tipicamente 15-30 min).

- [ ] **Step 2: Configura nginx.conf per HTTP (pre-SSL)**

Crea `/opt/restorix/nginx/nginx.conf` con configurazione HTTP-only per consentire la sfida ACME:

```nginx
events {}

http {
    server {
        listen 80;
        server_name restorix.edminformatica.it;

        location /.well-known/acme-challenge/ {
            root /var/www/certbot;
        }

        location / {
            return 301 https://$host$request_uri;
        }
    }
}
```

- [ ] **Step 3: Ottieni certificato SSL con certbot**

```bash
sudo apt-get install -y certbot
sudo certbot certonly --standalone \
  -d restorix.edminformatica.it \
  --email egidio.pescatore@edminformatica.com \
  --agree-tos --non-interactive
```

Output atteso: `Certificate is saved at: /etc/letsencrypt/live/restorix.edminformatica.it/fullchain.pem`

- [ ] **Step 4: Aggiorna nginx.conf con HTTPS**

```nginx
events { worker_connections 1024; }

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    upstream api {
        server api:8000;
    }

    server {
        listen 80;
        server_name restorix.edminformatica.it;
        return 301 https://$host$request_uri;
    }

    server {
        listen 443 ssl;
        server_name restorix.edminformatica.it;

        ssl_certificate /etc/letsencrypt/live/restorix.edminformatica.it/fullchain.pem;
        ssl_certificate_key /etc/letsencrypt/live/restorix.edminformatica.it/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;

        # Serve frontend SPA
        root /usr/share/nginx/html;
        index index.html;

        # Agent install script
        location /install.sh {
            alias /usr/share/nginx/html/install.sh;
            add_header Content-Type text/plain;
        }

        location /agent/ {
            alias /usr/share/nginx/html/agent/;
        }

        # API proxy
        location /api/ {
            proxy_pass http://api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_read_timeout 300s;
            client_max_body_size 50m;
        }

        # SPA fallback
        location / {
            try_files $uri $uri/ /index.html;
        }
    }
}
```

- [ ] **Step 5: Riavvia nginx con la nuova config**

```bash
cd /opt/restorix
docker compose restart nginx
```

- [ ] **Step 6: Verifica HTTPS**

```bash
curl -sk https://restorix.edminformatica.it/api/health
```

Output atteso: `{"status":"ok","app":"Restorix"}`

---

### Task 6: Smoke test produzione

- [ ] **Step 1: Login UI**

Apri https://restorix.edminformatica.it nel browser.

Verifica: pagina login carica, nessun errore console.

- [ ] **Step 2: Login con account admin**

Email: `egidio.pescatore@edminformatica.com`  
Password: quella impostata al Task 4 Step 5.

Verifica: redirect a Dashboard, sidebar visibile.

- [ ] **Step 3: Verifica assenza riferimenti licensing**

Vai su Settings. Verifica che NON ci sia un tab "Licenza".

- [ ] **Step 4: Crea un server MySQL**

Servers → Aggiungi server → Tipo: MySQL  
Verifica: placeholder porta è `3306`, label campo è "Host:Porta".

- [ ] **Step 5: Commit finale documentazione**

```bash
cd /d/Claude_Code/Restorix_Full
cat >> README.md << 'EOF'

## Produzione

- **URL:** https://restorix.edminformatica.it
- **Server:** egidio@46.225.106.181
- **Path:** /opt/restorix/
- **Aggiornamento:** `cd /opt/restorix && git pull && docker compose build && docker compose up -d`
EOF

git add README.md
git commit -m "docs: add production deployment info

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push
```

---

### Task 7: Rinnovo automatico SSL

- [ ] **Step 1: Aggiungi cron per rinnovo automatico**

```bash
sudo crontab -e
```

Aggiungi:
```
0 3 * * * certbot renew --quiet && docker exec restorix-nginx nginx -s reload
```

- [ ] **Step 2: Verifica dry-run rinnovo**

```bash
sudo certbot renew --dry-run
```

Output atteso: `Congratulations, all simulated renewals succeeded`
