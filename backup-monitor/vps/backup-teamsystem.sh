#!/usr/bin/env bash
# backup-teamsystem.sh — eseguito da cron alle 02:00 su ogni VPS
# Variabili d'ambiente lette da /etc/restic/restic.env

set -euo pipefail

ENV_FILE="/etc/restic/restic.env"
[[ -f "$ENV_FILE" ]] || { echo "ERRORE: $ENV_FILE non trovato"; exit 1; }
# shellcheck source=/dev/null
source "$ENV_FILE"

# Variabili richieste in restic.env:
# RESTIC_REPOSITORY, RESTIC_PASSWORD, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
# MASTER_URL, VPS_ID, API_KEY, TEAMSYSTEM_SERVICE, BACKUP_FOLDERS (spazio-separati)

MASTER_URL="${MASTER_URL:?}"
VPS_ID="${VPS_ID:?}"
API_KEY="${API_KEY:?}"
TEAMSYSTEM_SERVICE="${TEAMSYSTEM_SERVICE:-teamsystem}"
BACKUP_FOLDERS="${BACKUP_FOLDERS:-/home/Nativo}"

START_TS=$(date +%s)
STOP_TS=$START_TS
STATUS="failed"
SNAPSHOT_ID=""
SIZE_GB="0"
ERROR_MSG=""

# Ferma il servizio
systemctl stop "$TEAMSYSTEM_SERVICE" || true
STOP_TS=$(date +%s)

# Esegui backup
BACKUP_JSON=$(restic backup $BACKUP_FOLDERS --json 2>/dev/null | tail -1) || {
    ERROR_MSG="restic backup fallito"
}

# Riavvia il servizio
systemctl start "$TEAMSYSTEM_SERVICE" || true

END_TS=$(date +%s)
DOWNTIME_S=$((END_TS - STOP_TS))
DURATION_S=$((END_TS - START_TS))

if [[ -n "$BACKUP_JSON" && -z "$ERROR_MSG" ]]; then
    STATUS="ok"
    SNAPSHOT_ID=$(echo "$BACKUP_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('snapshot_id',''))" 2>/dev/null || echo "")
    SIZE_BYTES=$(echo "$BACKUP_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total_bytes_processed',0))" 2>/dev/null || echo "0")
    SIZE_GB=$(echo "scale=2; $SIZE_BYTES/1073741824" | bc)
fi

# Spazio disco libero
DISK_FREE_PCT=$(df /home --output=pcent | tail -1 | tr -d ' %')
DISK_FREE_PCT=$((100 - DISK_FREE_PCT))

# Cartelle come JSON array
FOLDERS_JSON=$(echo "$BACKUP_FOLDERS" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().split()))")

# Applica retention
restic forget --keep-daily 7 --keep-weekly 4 --prune --quiet || true

# Invia report al Master
curl -sf -X POST "$MASTER_URL/api/v1/backup/report" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d "{
        \"vps_id\": \"$VPS_ID\",
        \"status\": \"$STATUS\",
        \"snapshot_id\": \"$SNAPSHOT_ID\",
        \"size_gb\": $SIZE_GB,
        \"duration_s\": $DURATION_S,
        \"downtime_s\": $DOWNTIME_S,
        \"error_msg\": \"$ERROR_MSG\",
        \"folders\": $FOLDERS_JSON,
        \"disk_free_pct\": $DISK_FREE_PCT
    }" || echo "WARN: impossibile inviare report al Master"

exit 0
