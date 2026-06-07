#!/usr/bin/env bash
# restore-test-teamsystem.sh — eseguito da cron alle 03:30 su ogni VPS

set -uo pipefail

ENV_FILE="/etc/restic/restic.env"
source "$ENV_FILE"

MASTER_URL="${MASTER_URL:?}"
VPS_ID="${VPS_ID:?}"
API_KEY="${API_KEY:?}"
BACKUP_FOLDERS="${BACKUP_FOLDERS:-/home/Nativo}"
RESTORE_TMP="/tmp/restic-restore-test-$$"

STATUS="failed"
CHECKSUM_OK=0
DURATION_S=0
ERROR_MSG=""
START_TS=$(date +%s)

cleanup() { rm -rf "$RESTORE_TMP"; }
trap cleanup EXIT

# Recupera snapshot_id dell'ultimo backup riuscito
SNAPSHOT_ID=$(curl -sf "$MASTER_URL/api/v1/servers/$VPS_ID/latest-snapshot" \
    -H "X-API-Key: $API_KEY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('snapshot_id',''))" 2>/dev/null || echo "")

if [[ -z "$SNAPSHOT_ID" ]]; then
    ERROR_MSG="nessun snapshot disponibile"
else
    # File campione: il più recentemente modificato nella prima cartella
    FIRST_FOLDER=$(echo "$BACKUP_FOLDERS" | awk '{print $1}')
    SAMPLE_FILE=$(find "$FIRST_FOLDER" -type f -printf '%T@ %p\n' 2>/dev/null \
        | sort -rn | head -1 | awk '{print $2}')

    if [[ -z "$SAMPLE_FILE" ]]; then
        ERROR_MSG="nessun file trovato in $FIRST_FOLDER"
    else
        ORIG_CHECKSUM=$(sha256sum "$SAMPLE_FILE" | awk '{print $1}')
        RELATIVE_PATH="${SAMPLE_FILE#/}"

        mkdir -p "$RESTORE_TMP"
        restic restore "$SNAPSHOT_ID" \
            --target "$RESTORE_TMP" \
            --include "/$RELATIVE_PATH" --quiet 2>/dev/null || {
            ERROR_MSG="restic restore fallito"
        }

        if [[ -z "$ERROR_MSG" ]]; then
            RESTORED_FILE="$RESTORE_TMP/$RELATIVE_PATH"
            if [[ -f "$RESTORED_FILE" ]]; then
                RESTORED_CHECKSUM=$(sha256sum "$RESTORED_FILE" | awk '{print $1}')
                if [[ "$ORIG_CHECKSUM" == "$RESTORED_CHECKSUM" ]]; then
                    STATUS="ok"
                    CHECKSUM_OK=1
                else
                    ERROR_MSG="checksum mismatch: orig=$ORIG_CHECKSUM restored=$RESTORED_CHECKSUM"
                fi
            else
                ERROR_MSG="file ripristinato non trovato: $RESTORED_FILE"
            fi
        fi
    fi
fi

END_TS=$(date +%s)
DURATION_S=$((END_TS - START_TS))

curl -sf -X POST "$MASTER_URL/api/v1/restore/report" \
    -H "Content-Type: application/json" \
    -H "X-API-Key: $API_KEY" \
    -d "{
        \"vps_id\": \"$VPS_ID\",
        \"status\": \"$STATUS\",
        \"checksum_ok\": $CHECKSUM_OK,
        \"duration_s\": $DURATION_S,
        \"error_msg\": \"$ERROR_MSG\"
    }" || echo "WARN: impossibile inviare report restore al Master"

exit 0
