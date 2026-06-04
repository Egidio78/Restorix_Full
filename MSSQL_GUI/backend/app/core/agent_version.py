"""Single source of truth for Restorix backend & agent versions.

Bumped together with `agent/dbshield_agent/__init__.py __version__`.
Used by:
- GET /api/v1/agent/version
- GET /api/v1/agent/install-script (rendered into install.sh)
- nginx download path /agent/dbshield-agent-<VERSION>.tar.gz
"""

RESTORIX_VERSION = "1.4.0"
AGENT_VERSION = "1.4.1"
