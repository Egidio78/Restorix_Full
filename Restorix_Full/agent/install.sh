#!/usr/bin/env bash
set -euo pipefail

# Restorix Agent Installer
# Usage: curl -sSL https://backupdb.edminformatica.it/install.sh | bash -s -- --token=TOKEN_HERE

AGENT_VERSION="1.0.0"
PLATFORM_URL="https://restorix.edminformatica.it"
INSTALL_DIR="/opt/restorix-agent"
CONFIG_DIR="/etc/restorix-agent"
SERVICE_NAME="restorix-agent"
AGENT_USER="restorix"
LOG_DIR="/var/log/restorix-agent"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# Parse args
TOKEN=""
for arg in "$@"; do
    case $arg in
        --token=*) TOKEN="${arg#*=}" ;;
        --token)   shift; TOKEN="$1" ;;
    esac
done

[ -z "$TOKEN" ] && error "Missing --token argument. Get your token from the Restorix dashboard."

# Must be root
[ "$EUID" -ne 0 ] && error "This script must be run as root"

info "Restorix Agent v${AGENT_VERSION} installer"
info "Platform: ${PLATFORM_URL}"
echo

# Detect OS
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS_ID="${ID}"
    OS_VERSION="${VERSION_ID:-}"
else
    OS_ID="unknown"
fi
info "Detected OS: ${OS_ID} ${OS_VERSION}"

# Install Python 3 (>= 3.8 supported via __future__ annotations)
PYTHON_CMD=""

install_python() {
    # Prefer newer Python if already available
    for candidate in python3.12 python3.11 python3.10 python3.9 python3.8 python3; do
        if command -v "$candidate" &>/dev/null; then
            PY_MAJ=$("$candidate" -c 'import sys; print(sys.version_info.major)')
            PY_MIN=$("$candidate" -c 'import sys; print(sys.version_info.minor)')
            if [ "$PY_MAJ" -eq 3 ] && [ "$PY_MIN" -ge 8 ]; then
                PYTHON_CMD="$candidate"
                info "Python found: $($candidate --version 2>&1)"
                return 0
            fi
        fi
    done

    # Install python3 from system repos (no PPA needed)
    info "Installing Python 3 from system repositories..."
    case "${OS_ID}" in
        ubuntu|debian)
            apt-get update -qq
            apt-get install -y -qq python3 python3-venv python3-distutils python3-pip
            ;;
        centos|rhel|rocky|almalinux)
            yum install -y python3 python3-pip 2>/dev/null || dnf install -y python3 python3-pip
            ;;
        fedora)
            dnf install -y python3
            ;;
        *)
            error "Unsupported OS: ${OS_ID}. Install Python 3.8+ manually and re-run." ;;
    esac
    PYTHON_CMD="python3"
    success "Python installed: $($PYTHON_CMD --version 2>&1)"
}

install_python

# Install pip if missing
if ! "$PYTHON_CMD" -m pip --version &>/dev/null; then
    info "Installing pip..."
    PY_MINOR=$("$PYTHON_CMD" -c 'import sys; print(sys.version_info.minor)')
    PY_MAJOR=$("$PYTHON_CMD" -c 'import sys; print(sys.version_info.major)')
    if [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -le 9 ]; then
        curl -sSL "https://bootstrap.pypa.io/pip/${PY_MAJOR}.${PY_MINOR}/get-pip.py" | "$PYTHON_CMD" -
    else
        curl -sSL https://bootstrap.pypa.io/get-pip.py | "$PYTHON_CMD" -
    fi
fi

# Check sqlcmd (warn only)
if ! command -v sqlcmd &>/dev/null; then
    warn "sqlcmd not found. Install mssql-tools to enable MSSQL backups:"
    warn "  Ubuntu/Debian: https://docs.microsoft.com/sql/linux/sql-server-linux-setup-tools"
    warn "  Agent will install but backups will fail until sqlcmd is available."
fi

# Create agent user
if ! id "${AGENT_USER}" &>/dev/null; then
    info "Creating service user '${AGENT_USER}'..."
    useradd --system --no-create-home --shell /usr/sbin/nologin "${AGENT_USER}"
fi

# If SQL Server is installed locally, share a backup directory with the mssql user
if id mssql &>/dev/null; then
    info "Local SQL Server detected — configuring shared backup directory"
    usermod -a -G mssql "${AGENT_USER}" 2>/dev/null || true
    TEMP_DIR="/var/opt/mssql/backups/restorix"
    mkdir -p "${TEMP_DIR}"
    chown mssql:mssql "${TEMP_DIR}"
    chmod 770 "${TEMP_DIR}"
else
    TEMP_DIR="/tmp/restorix"
    mkdir -p "${TEMP_DIR}"
    chown "${AGENT_USER}:${AGENT_USER}" "${TEMP_DIR}"
fi

# Create directories
info "Creating directories..."
mkdir -p "${INSTALL_DIR}" "${CONFIG_DIR}" "${LOG_DIR}"
chown "${AGENT_USER}:${AGENT_USER}" "${LOG_DIR}"

# Ensure venv module is available for the selected Python
if ! "$PYTHON_CMD" -c "import ensurepip" >/dev/null 2>&1; then
    info "venv missing for ${PYTHON_CMD} — installing..."
    if [ "${OS_ID}" = "ubuntu" ] || [ "${OS_ID}" = "debian" ]; then
        PY_MINOR=$("$PYTHON_CMD" -c "import sys; print('%d.%d' % sys.version_info[:2])")
        apt-get install -y -qq "python${PY_MINOR}-venv" 2>/dev/null \
            || apt-get install -y -qq python3-venv python3-full
    fi
fi

# Create virtualenv
info "Creating Python virtual environment at ${INSTALL_DIR}..."
"$PYTHON_CMD" -m venv "${INSTALL_DIR}/venv"
"${INSTALL_DIR}/venv/bin/pip" install --quiet --upgrade pip

# Install dependencies
info "Installing agent dependencies..."
"${INSTALL_DIR}/venv/bin/pip" install --quiet     requests     boto3     paramiko     cryptography

# Download and install agent package from platform
info "Downloading agent package..."
AGENT_PKG_URL="${PLATFORM_URL}/agent/restorix-agent-${AGENT_VERSION}.tar.gz"
AGENT_PKG="/tmp/restorix-agent-${AGENT_VERSION}.tar.gz"

if curl -sSLf -o "${AGENT_PKG}" "${AGENT_PKG_URL}" 2>/dev/null; then
    "${INSTALL_DIR}/venv/bin/pip" install --quiet "${AGENT_PKG}"
    rm -f "${AGENT_PKG}"
    success "Agent package installed from platform"
else
    warn "Could not download agent package from platform. Please re-run after the platform is fully set up."
fi

# Write config
info "Writing configuration to ${CONFIG_DIR}/config.json..."
cat > "${CONFIG_DIR}/config.json" << CONFIGEOF
{
  "api_url": "${PLATFORM_URL}",
  "agent_token": "${TOKEN}",
  "poll_interval_seconds": 30,
  "log_level": "INFO",
  "temp_dir": "${TEMP_DIR}"
}
CONFIGEOF
chmod 640 "${CONFIG_DIR}/config.json"
chown root:"${AGENT_USER}" "${CONFIG_DIR}/config.json"

# ── systemd plumbing + auto-updater ──────────────────────────────────────
# Single source of truth lives in the agent package (dbshield_agent.bootstrap).
# It writes the agent service (with RuntimeDirectory), update.sh, the update
# path-unit (instant heartbeat trigger) and the fallback timer, then enables +
# starts everything. The updater re-runs this on each package update, so the
# plumbing self-heals and never needs a manual touch again.
info "Installing systemd plumbing via bootstrap..."
if [ -x "${INSTALL_DIR}/venv/bin/restorix-agent-bootstrap" ]; then
    "${INSTALL_DIR}/venv/bin/restorix-agent-bootstrap"
else
    error "Agent package not installed (bootstrap missing). Re-run after the platform is reachable."
fi

sleep 2
if systemctl is-active --quiet "${SERVICE_NAME}"; then
    success "Restorix Agent is running!"
else
    warn "Agent service may not have started. Check logs: journalctl -u ${SERVICE_NAME} -n 20"
fi

echo
success "Installation complete!"
echo
echo "  Token:    ${TOKEN}"
echo "  Platform: ${PLATFORM_URL}"
echo "  Config:   ${CONFIG_DIR}/config.json"
echo "  Logs:     ${LOG_DIR}/agent.log"
echo "  Service:  systemctl status ${SERVICE_NAME}"
echo
info "The agent will appear online in the Restorix dashboard within 30 seconds."
