"""Single source of truth for the latest published agent version.

To publish a new agent build:
  1. bump LATEST_AGENT_VERSION here
  2. bump __version__ in agent/dbshield_agent/__init__.py to the same value
  3. rebuild the tarball and drop it into the shared host dir agent-dist/
     (served by nginx at /agent/ and read by the API for SHA256)

The SHA256 is computed at runtime from the exact file the API/nginx serve,
so there is nothing to keep manually in sync.
"""
import hashlib
import os
import threading

LATEST_AGENT_VERSION = "1.2.2"
AGENT_PACKAGE_FILENAME = "restorix-agent-1.0.0.tar.gz"

# Directory shared (read-only) with nginx; holds the served tarball.
AGENT_DIST_DIR = os.environ.get("AGENT_DIST_DIR", "/agent-dist")

_sha_lock = threading.Lock()
_sha_cache: dict[str, tuple[float, str]] = {}


def agent_package_path() -> str:
    return os.path.join(AGENT_DIST_DIR, AGENT_PACKAGE_FILENAME)


def agent_package_sha256() -> str | None:
    """SHA256 of the served tarball, cached by file mtime. None if unavailable."""
    path = agent_package_path()
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    with _sha_lock:
        cached = _sha_cache.get(path)
        if cached and cached[0] == mtime:
            return cached[1]
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
    except OSError:
        return None
    digest = h.hexdigest()
    with _sha_lock:
        _sha_cache[path] = (mtime, digest)
    return digest


def agent_download_url() -> str:
    return f"/agent/{AGENT_PACKAGE_FILENAME}"
