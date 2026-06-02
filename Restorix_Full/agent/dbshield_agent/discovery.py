from __future__ import annotations
"""Database discovery via sqlcmd."""
import logging
import subprocess

logger = logging.getLogger(__name__)


def discover_databases(mssql_instance: str, username: str, password: str):
    cmd = [
        "sqlcmd",
        "-S", mssql_instance,
        "-Q", "SET NOCOUNT ON; SELECT name FROM sys.databases WHERE database_id > 4 ORDER BY name",
        "-h", "-1",
        "-W",
        "-b",
        "-C",  # Trust server certificate (per ODBC 18 con cert self-signed)
        "-N", "o",  # Encrypt connection se possibile, opzionale
    ]
    if username:
        cmd += ["-U", username, "-P", password]
    else:
        cmd += ["-E"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return [], f"sqlcmd failed: {result.stderr or result.stdout}"
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip() and not line.startswith("--")]
        databases = [l for l in lines if l and not l.startswith("(") and not l.lower().startswith("changed")]
        return databases, None
    except FileNotFoundError:
        return [], "sqlcmd not installed on this server"
    except Exception as e:
        return [], f"Discovery error: {e}"
