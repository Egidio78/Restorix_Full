#!/usr/bin/env bash
set -euo pipefail

# DBShield Agent Installer
# Usage: curl -sSL https://backupdb.edminformatica.it/install.sh | bash -s -- --token=TOKEN_HERE

AGENT_VERSION="1.0.0"
PLATFORM_URL="https://backupdb.edminformatica.it"
INSTALL_DIR="/opt/dbshield-agent"
CONFIG_DIR="/etc/dbshield-agent"
SERVICE_NAME="dbshield-agent"
AGENT_USER="dbshield"
LOG_DIR="/var/log/dbshield-agent"

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

[ -z "$TOKEN" ] && error "Missing --token argument. Get your token from the DBShield dashboard."

# Must be root
[ "$EUID" -ne 0 ] && error "This script must be run as root"

info "DBShield Agent v${AGENT_VERSION} installer"
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

# Install Python 3
install_python() {
    if command -v python3 &>/dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        info "Python found: ${PYTHON_VERSION}"
        return 0
    fi
    info "Installing Python 3..."
    case "${OS_ID}" in
        ubuntu|debian)
            apt-get update -qq && apt-get install -y -qq python3 python3-pip python3-venv ;;
        centos|rhel|rocky|almalinux)
            yum install -y python3 python3-pip 2>/dev/null || dnf install -y python3 python3-pip ;;
        fedora)
            dnf install -y python3 python3-pip ;;
        *)
            error "Unsupported OS: ${OS_ID}. Install Python 3.9+ manually." ;;
    esac
    success "Python installed"
}

install_python

# Install pip if missing
if ! python3 -m pip --version &>/dev/null; then
    info "Installing pip..."
    curl -sSL https://bootstrap.pypa.io/get-pip.py | python3 -
fi

# Check sqlcmd (warn only)
if ! command -v sqlcmd &>/dev/null; then
    warn "sqlcmd not found. Install mssql-tools to enable MSSQL backups:"
    warn "  Ubuntu/Debian: https://docs.microsoft.com/sql/linux/sql-server-linux-setup-tools"
    warn "  Agent will install but backups will fail until sqlcmd is available."
fi

# Verifica/installazione mysql client (per backup MySQL)
if ! command -v mysqldump &>/dev/null; then
    echo "mysqldump non trovato. Tentativo installazione default-mysql-client..."
    if command -v apt-get &>/dev/null; then
        apt-get install -y default-mysql-client 2>/dev/null && echo "mysql-client installato." || \
            echo "WARNING: impossibile installare mysql-client. I backup MySQL falliranno."
    elif command -v yum &>/dev/null; then
        yum install -y mysql 2>/dev/null && echo "mysql installato." || \
            echo "WARNING: impossibile installare mysql. I backup MySQL falliranno."
    else
        echo "WARNING: mysqldump non trovato. I backup MySQL falliranno."
    fi
else
    echo "mysqldump trovato: $(which mysqldump)"
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
    TEMP_DIR="/var/opt/mssql/backups/dbshield"
    mkdir -p "${TEMP_DIR}"
    chown mssql:mssql "${TEMP_DIR}"
    chmod 770 "${TEMP_DIR}"
else
    TEMP_DIR="/tmp/dbshield"
    mkdir -p "${TEMP_DIR}"
    chown "${AGENT_USER}:${AGENT_USER}" "${TEMP_DIR}"
fi

# Create directories
info "Creating directories..."
mkdir -p "${INSTALL_DIR}" "${CONFIG_DIR}" "${LOG_DIR}"
chown "${AGENT_USER}:${AGENT_USER}" "${LOG_DIR}"

# Ensure python3-venv module is available (often missing on Debian/Ubuntu)
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
    info "python3-venv missing — installing..."
    if [ "${OS_ID}" = "ubuntu" ] || [ "${OS_ID}" = "debian" ]; then
        PY_MINOR=$(python3 -c "import sys; print('%d.%d' % sys.version_info[:2])")
        apt-get install -y -qq "python${PY_MINOR}-venv" python3-venv python3-full 2>/dev/null \
            || apt-get install -y -qq python3-venv python3-full
    fi
fi

# Create virtualenv
info "Creating Python virtual environment at ${INSTALL_DIR}..."
python3 -m venv "${INSTALL_DIR}/venv"
"${INSTALL_DIR}/venv/bin/pip" install --quiet --upgrade pip

# Install dependencies
info "Installing agent dependencies..."
"${INSTALL_DIR}/venv/bin/pip" install --quiet     requests     boto3     paramiko     cryptography

# Download and install agent package from platform
info "Downloading agent package..."
AGENT_PKG_URL="${PLATFORM_URL}/agent/dbshield-agent-${AGENT_VERSION}.tar.gz"
AGENT_PKG="/tmp/dbshield-agent-${AGENT_VERSION}.tar.gz"

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

# Create systemd service
info "Creating systemd service..."
cat > "/etc/systemd/system/${SERVICE_NAME}.service" << SERVICEEOF
[Unit]
Description=DBShield Backup Agent
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=${AGENT_USER}
Group=${AGENT_USER}
ExecStart=${INSTALL_DIR}/venv/bin/dbshield-agent
Environment=DBSHIELD_CONFIG=${CONFIG_DIR}/config.json
Restart=always
RestartSec=10
StandardOutput=append:${LOG_DIR}/agent.log
StandardError=append:${LOG_DIR}/agent.log

[Install]
WantedBy=multi-user.target
SERVICEEOF

# Reload and enable service
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

sleep 2
if systemctl is-active --quiet "${SERVICE_NAME}"; then
    success "DBShield Agent is running!"
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
info "The agent will appear online in the DBShield dashboard within 30 seconds."
