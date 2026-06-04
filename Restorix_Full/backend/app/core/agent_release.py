"""Single source of truth for the latest published agent version.

When you publish a new agent build:
  1. bump LATEST_AGENT_VERSION here
  2. bump __version__ in agent/dbshield_agent/__init__.py to the same value
  3. rebuild the agent tarball and upload it to nginx at AGENT_PACKAGE_PATH

Installed agents poll GET /agent/update-check; if their running version differs
from LATEST_AGENT_VERSION (or an update was requested from the UI), the root
updater (systemd timer) downloads and installs this build, then restarts.
"""

LATEST_AGENT_VERSION = "1.1.0"
# Path served by nginx (filename is version-independent so the updater URL is stable)
AGENT_PACKAGE_FILENAME = "restorix-agent-1.0.0.tar.gz"
