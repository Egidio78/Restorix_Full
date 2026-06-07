#!/usr/bin/env bash
# backup-teamsystem.sh — eseguito da cron alle 02:00 su ogni VPS
# Variabili d'ambiente lette da /etc/restic/restic.env

set -uo pipefail

ENV_FILE="/etc/restic/restic.env"
[[ -f "$ENV_FILE" ]] || { echo "ERRORE: $ENV_FILE non trovato"; exit 1; }
# shellcheck source=/dev/null
source "$ENV_FILE"

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

# Esegui backup (usa array per supportare percorsi con spazi)
read -ra BACKUP_ARRAY <<< "$BACKUP_FOLDERS"
BACKUP_JSON=$(restic backup "${BACKUP_ARRAY[@]}" --json 2>/dev/null | tail -1) || {
    ERROR_MSG="restic backup fallito"
}

# Riavvia il servizio (sempre, anche in caso di errore)
systemctl start "$TEAMSYSTEM_SERVICE" || true

END_TS=$(date +%s)
DOWNTIME_S=$((END_TS - STOP_TS))
DURATION_S=$((END_TS - START_TS))

if [[ -n "$BACKUP_JSON" && -z "$ERROR_MSG" ]]; then
    STATUS="ok"
    SNAPSHOT_ID=$(echo "$BACKUP_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('snapshot_id',''))" 2>/dev/null || echo "")
    SIZE_BYTES=$(echo "$BACKUP_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('total_bytes_processed',0))" 2>/dev/null || echo "0")
    SIZE_GB=$(echo "scale=2; $SIZE_BYTES/1073741824" | bc 2>/dev/null || echo "0")
fi

# Spazio disco libero (non fatale se fallisce)
DISK_FREE_PCT=$(df /home --output=pcent 2>/dev/null | tail -1 | tr -d ' %' || echo "0")
DISK_FREE_PCT=$((100 - DISK_FREE_PCT))

# Cartelle come JSON array
FOLDERS_JSON=$(echo "$BACKUP_FOLDERS" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().split()))" 2>/dev/null || echo '[]')

# Applica retention (scoped a questo host)
restic forget --keep-daily 7 --keep-weekly 4 --prune --host "$HOSTNAME" --quiet 2>/dev/null || true

# Costruisci payload JSON in modo sicuro
JSON_PAYLOAD=$(python3 -c "
import json, sys
print(json.dumps({
    'vps_id': '$VPS_ID',
    'status': '$STATUS',
    'snapshot_id': '$SNAPSHOT_ID',
    'size_gb': float('$SIZE_GB') if '$SIZE_GB' else 0,
    'duration_s': int('$DURATION_S'),
    'downtime_s': int('$DOWNTIME_S'),
    'error_msg': '$ERROR_MSG',
    'folders': $FOLDERS_JSON,
    'disk_free_pct': int('$DISK_FREE_PCT'),
}))
" 2>/dev/null) || JSON_PAYLOAD="{\"vps_id\":\"$VPS_ID\",\"status\":\"failed\",\"error_msg\":\"payload build failed\"}"

# Invia report al Master
curl -sf -X POST "$MASTER_URL/api/v1/backup/report" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d "$JSON_PAYLOAD" || echo "WARN: impossibile inviare report al Master"

exit 0
