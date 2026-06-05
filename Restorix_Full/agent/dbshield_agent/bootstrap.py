from __future__ import annotations
"""Root bootstrap: (re)writes the agent's systemd plumbing + updater script.

Single source of truth for update.sh and the systemd units. Run as root by
install.sh on first install AND by the updater after each package update, so the
plumbing self-heals/self-updates and never needs a manual touch again.
"""
import os
import subprocess
import sys

INSTALL_DIR = "/opt/restorix-agent"
CONFIG_DIR = "/etc/restorix-agent"
LOG_DIR = "/var/log/restorix-agent"
SERVICE_NAME = "restorix-agent"
AGENT_USER = "restorix"

# ── The root updater script ───────────────────────────────────────────────
UPDATE_SH = r'''#!/usr/bin/env bash
# Restorix agent self-updater (runs as root). Triggered by the path-unit when the
# agent drops /run/restorix-agent/update.json, or periodically by the timer.
set -u
CONFIG="/etc/restorix-agent/config.json"
VENV="/opt/restorix-agent/venv"
SERVICE="restorix-agent"
TRIGGER="/run/restorix-agent/update.json"
PY="${VENV}/bin/python"

[ -f "${CONFIG}" ] || exit 0
API=$("${PY}" -c "import json;print(json.load(open('${CONFIG}'))['api_url'])" 2>/dev/null) || exit 0
TOKEN=$("${PY}" -c "import json;print(json.load(open('${CONFIG}'))['agent_token'])" 2>/dev/null) || exit 0
CURRENT=$("${PY}" -c "from dbshield_agent import __version__;print(__version__)" 2>/dev/null || echo "0.0.0")

URL=""; SHA=""; VERSION=""
# Lock-rename the trigger so a failed run doesn't loop re-processing it.
if [ -f "${TRIGGER}" ]; then
    mv "${TRIGGER}" "${TRIGGER}.processing" 2>/dev/null || true
fi
if [ -f "${TRIGGER}.processing" ]; then
    URL=$("${PY}" -c "import json;print(json.load(open('${TRIGGER}.processing')).get('download_url',''))" 2>/dev/null)
    SHA=$("${PY}" -c "import json;print(json.load(open('${TRIGGER}.processing')).get('sha256',''))" 2>/dev/null)
    VERSION=$("${PY}" -c "import json;print(json.load(open('${TRIGGER}.processing')).get('version',''))" 2>/dev/null)
    rm -f "${TRIGGER}.processing"
else
    RESP=$(curl -sf --max-time 20 "${API}/api/v1/agent/update-check?token=${TOKEN}&current=${CURRENT}") || exit 0
    SHOULD=$(printf '%s' "${RESP}" | "${PY}" -c "import sys,json;print(json.load(sys.stdin).get('should_update'))" 2>/dev/null)
    [ "${SHOULD}" = "True" ] || exit 0
    URL=$(printf '%s' "${RESP}" | "${PY}" -c "import sys,json;print(json.load(sys.stdin).get('download_url',''))" 2>/dev/null)
    SHA=$(printf '%s' "${RESP}" | "${PY}" -c "import sys,json;print(json.load(sys.stdin).get('sha256',''))" 2>/dev/null)
    VERSION=$(printf '%s' "${RESP}" | "${PY}" -c "import sys,json;print(json.load(sys.stdin).get('latest_version',''))" 2>/dev/null)
fi
# Normalise the Python None-stringified values
[ "${URL}" = "None" ] && URL=""
[ "${SHA}" = "None" ] && SHA=""
[ "${VERSION}" = "None" ] && VERSION=""
[ -n "${URL}" ] || exit 0

case "${URL}" in http*) FULL="${URL}" ;; *) FULL="${API}${URL}" ;; esac
report_fail() { curl -sf --max-time 15 -X POST "${API}/api/v1/agent/update-done?token=${TOKEN}&success=false" >/dev/null 2>&1 || true; }

echo "[restorix-update] updating ${CURRENT} -> ${VERSION} ..."
curl -sSLf --max-time 180 "${FULL}" -o /tmp/ra-update.tar.gz || { echo "download failed"; report_fail; exit 1; }

if [ -n "${SHA}" ]; then
    ACTUAL=$("${PY}" -c "import hashlib;print(hashlib.sha256(open('/tmp/ra-update.tar.gz','rb').read()).hexdigest())" 2>/dev/null)
    if [ "${ACTUAL}" != "${SHA}" ]; then
        echo "[restorix-update] SHA256 mismatch"; rm -f /tmp/ra-update.tar.gz; report_fail; exit 1
    fi
fi

SITEPKG=$("${PY}" -c "import dbshield_agent,os;print(os.path.dirname(dbshield_agent.__file__))" 2>/dev/null)
BACKUP="/tmp/ra-pkg-backup.$$"
[ -n "${SITEPKG}" ] && cp -a "${SITEPKG}" "${BACKUP}" 2>/dev/null || true

if ! "${VENV}/bin/pip" install --quiet --force-reinstall --no-deps /tmp/ra-update.tar.gz; then
    echo "[restorix-update] pip install failed, rolling back"
    [ -d "${BACKUP}" ] && [ -n "${SITEPKG}" ] && { rm -rf "${SITEPKG}"; cp -a "${BACKUP}" "${SITEPKG}"; }
    rm -rf "${BACKUP}" /tmp/ra-update.tar.gz; report_fail; exit 1
fi
rm -f /tmp/ra-update.tar.gz

# Refresh systemd plumbing from the just-installed package (self-healing).
"${VENV}/bin/restorix-agent-bootstrap" --no-restart >/dev/null 2>&1 || true

systemctl restart "${SERVICE}"
sleep 4
NEW=$("${PY}" -c "from dbshield_agent import __version__;print(__version__)" 2>/dev/null || echo "")
if systemctl is-active --quiet "${SERVICE}" && [ -n "${NEW}" ]; then
    rm -rf "${BACKUP}"
    curl -sf --max-time 15 -X POST "${API}/api/v1/agent/update-done?token=${TOKEN}&version=${NEW}&success=true" >/dev/null 2>&1 || true
    echo "[restorix-update] updated to ${NEW}"
else
    echo "[restorix-update] agent did not start, rolling back"
    if [ -d "${BACKUP}" ] && [ -n "${SITEPKG}" ]; then
        rm -rf "${SITEPKG}"; cp -a "${BACKUP}" "${SITEPKG}"
        if systemctl restart "${SERVICE}"; then
            rm -rf "${BACKUP}"
        else
            echo "[restorix-update] CRITICAL: rollback restart failed, backup kept at ${BACKUP}"
        fi
    fi
    report_fail
fi
'''

AGENT_SERVICE = f'''[Unit]
Description=Restorix Backup Agent
After=network.target
Wants=network-online.target

[Service]
Type=simple
User={AGENT_USER}
Group={AGENT_USER}
ExecStart={INSTALL_DIR}/venv/bin/restorix-agent
Environment=RESTORIX_CONFIG={CONFIG_DIR}/config.json
RuntimeDirectory=restorix-agent
RuntimeDirectoryMode=0770
RuntimeDirectoryPreserve=yes
Restart=always
RestartSec=10
StandardOutput=append:{LOG_DIR}/agent.log
StandardError=append:{LOG_DIR}/agent.log

[Install]
WantedBy=multi-user.target
'''

UPDATE_SERVICE = f'''[Unit]
Description=Restorix Agent Auto-Updater
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart={INSTALL_DIR}/update.sh
'''

UPDATE_PATH = f'''[Unit]
Description=Restorix Agent update trigger watcher

[Path]
PathExists=/run/restorix-agent/update.json
Unit={SERVICE_NAME}-update.service

[Install]
WantedBy=paths.target
'''

UPDATE_TIMER = f'''[Unit]
Description=Restorix Agent Auto-Updater timer (fallback)

[Timer]
OnBootSec=2min
OnUnitActiveSec=15min
Unit={SERVICE_NAME}-update.service

[Install]
WantedBy=timers.target
'''

COMMAND_SERVICE = f'''[Unit]
Description=Restorix Agent Root Command Runner
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart={INSTALL_DIR}/venv/bin/restorix-agent-root
'''

COMMAND_PATH = f'''[Unit]
Description=Restorix Agent root command trigger watcher

[Path]
PathExists=/run/restorix-agent/command.json
Unit={SERVICE_NAME}-command.service

[Install]
WantedBy=paths.target
'''


def _write(path: str, content: str, mode: int = 0o644) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(content)
    os.chmod(tmp, mode)
    os.replace(tmp, path)


def main() -> int:
    if os.geteuid() != 0:
        print("restorix-agent-bootstrap must run as root", file=sys.stderr)
        return 1

    no_restart = "--no-restart" in sys.argv

    _write(os.path.join(INSTALL_DIR, "update.sh"), UPDATE_SH, 0o755)
    _write(f"/etc/systemd/system/{SERVICE_NAME}.service", AGENT_SERVICE)
    _write(f"/etc/systemd/system/{SERVICE_NAME}-update.service", UPDATE_SERVICE)
    _write(f"/etc/systemd/system/{SERVICE_NAME}-update.path", UPDATE_PATH)
    _write(f"/etc/systemd/system/{SERVICE_NAME}-update.timer", UPDATE_TIMER)
    _write(f"/etc/systemd/system/{SERVICE_NAME}-command.service", COMMAND_SERVICE)
    _write(f"/etc/systemd/system/{SERVICE_NAME}-command.path", COMMAND_PATH)

    subprocess.run(["systemctl", "daemon-reload"], check=False)
    subprocess.run(["systemctl", "enable", f"{SERVICE_NAME}.service"], check=False)
    subprocess.run(["systemctl", "enable", "--now", f"{SERVICE_NAME}-update.path"], check=False)
    subprocess.run(["systemctl", "enable", "--now", f"{SERVICE_NAME}-update.timer"], check=False)
    subprocess.run(["systemctl", "enable", "--now", f"{SERVICE_NAME}-command.path"], check=False)
    if not no_restart:
        subprocess.run(["systemctl", "restart", f"{SERVICE_NAME}.service"], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
