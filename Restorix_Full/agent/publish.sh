#!/usr/bin/env bash
# Publish a new Restorix agent version in one command.
#
#   ./publish.sh 1.2.0
#
# Does everything: bumps the version in both source files, rebuilds the tarball,
# uploads it to the platform's shared agent-dist dir (served by nginx + read by
# the API for SHA256), and bumps LATEST_AGENT_VERSION in the backend.
# After this, every agent auto-updates on its own — no per-server action.
set -euo pipefail

VERSION="${1:-}"
if ! printf '%s' "$VERSION" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+$'; then
    echo "Usage: ./publish.sh X.Y.Z   (e.g. ./publish.sh 1.2.0)" >&2
    exit 1
fi

# --- config (override via env) ---
SSH_KEY="${RESTORIX_SSH_KEY:-$HOME/.ssh/codex_awx}"
SSH_HOST="${RESTORIX_SSH_HOST:-egidio@46.225.106.181}"
REMOTE_DIR="${RESTORIX_REMOTE_DIR:-/opt/restorix}"
AGENT_DIST="${REMOTE_DIR}/agent-dist/restorix-agent-1.0.0.tar.gz"

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "${HERE}/.." && pwd)"
SSH="ssh -i ${SSH_KEY} -o StrictHostKeyChecking=no"
SCP="scp -i ${SSH_KEY} -o StrictHostKeyChecking=no"

echo "==> Bumping version to ${VERSION}"
# agent __init__.py
printf 'from __future__ import annotations\n__version__ = "%s"\n' "${VERSION}" > "${HERE}/dbshield_agent/__init__.py"
# backend LATEST_AGENT_VERSION
python - "$REPO" "$VERSION" <<'PY'
import re, sys, pathlib
repo, ver = sys.argv[1], sys.argv[2]
p = pathlib.Path(repo) / "backend" / "app" / "core" / "agent_release.py"
s = p.read_text()
s = re.sub(r'LATEST_AGENT_VERSION = "[^"]*"', f'LATEST_AGENT_VERSION = "{ver}"', s)
p.write_text(s)
print("  backend LATEST_AGENT_VERSION ->", ver)
PY

echo "==> Building tarball"
cd "${HERE}"
rm -rf dist build *.egg-info
python setup.py sdist >/dev/null 2>&1
# Use relative paths: native Windows Python can't read git-bash /d/... paths.
TARBALL="dist/restorix_agent-1.0.0.tar.gz"
[ -f "${TARBALL}" ] || { echo "build failed: ${TARBALL} not found" >&2; exit 1; }
SHA=$(python -c "import hashlib;print(hashlib.sha256(open('${TARBALL}','rb').read()).hexdigest())")
echo "  sha256: ${SHA}"

echo "==> Uploading to ${SSH_HOST}:${AGENT_DIST} (atomic)"
# Upload to a temp name then rename on the server, so the API never computes the
# SHA256 over a half-written file and agents never download a partial tarball.
${SCP} "${TARBALL}" "${SSH_HOST}:${AGENT_DIST}.tmp"
${SSH} "${SSH_HOST}" "mv -f ${AGENT_DIST}.tmp ${AGENT_DIST}"
${SCP} "install.sh" "${SSH_HOST}:${REMOTE_DIR}/agent-dist/install.sh.tmp"
${SSH} "${SSH_HOST}" "mv -f ${REMOTE_DIR}/agent-dist/install.sh.tmp ${REMOTE_DIR}/agent-dist/install.sh"

echo "==> Rebuilding API so it serves LATEST_AGENT_VERSION=${VERSION}"
${SCP} "${REPO}/backend/app/core/agent_release.py" "${SSH_HOST}:${REMOTE_DIR}/backend/app/core/agent_release.py"
${SSH} "${SSH_HOST}" "cd ${REMOTE_DIR} && docker compose build api >/dev/null 2>&1 && docker compose up -d api >/dev/null 2>&1 && sleep 6 && docker exec restorix-nginx-1 nginx -s reload >/dev/null 2>&1 || true"

echo "==> Verifying"
LIVE=$(curl -sk https://restorix.edminformatica.it/api/v1/agent/version)
echo "  platform reports: ${LIVE}"
echo ""
echo "✅ Published v${VERSION}. All agents will auto-update within ~30s (heartbeat) or ~15min (timer fallback)."
echo "   Remember to: git add -A && git commit && git push"
