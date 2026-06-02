from __future__ import annotations
import hashlib
import logging
import os
import subprocess
from datetime import datetime

logger = logging.getLogger(__name__)


def create_backup(mssql_instance: str, db_name: str, username: str, password: str, temp_dir: str, native_compression: bool = False, name_prefix: str = "") -> str:
    os.makedirs(temp_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"{name_prefix}_{db_name}" if name_prefix else db_name
    bak_file = os.path.join(temp_dir, f"{base}_{timestamp}.bak")

    compression_clause = "COMPRESSION, " if native_compression else ""
    tsql = (
        f"BACKUP DATABASE [{db_name}] TO DISK = N'{bak_file}' "
        f"WITH {compression_clause}NOFORMAT, NOINIT, NAME = N'{db_name} Full Backup', "
        f"SKIP, NOREWIND, NOUNLOAD, STATS = 10"
    )

    cmd = ["sqlcmd", "-S", mssql_instance, "-Q", tsql, "-b", "-C", "-N", "o"]
    if username:
        cmd += ["-U", username, "-P", password]
    else:
        cmd += ["-E"]

    logger.info(f"Starting backup of {db_name} on {mssql_instance}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        if result.returncode != 0:
            raise RuntimeError(f"sqlcmd failed (exit {result.returncode}): {result.stderr or result.stdout}")
    except FileNotFoundError:
        raise RuntimeError("sqlcmd not found. Install mssql-tools.")

    if not os.path.exists(bak_file):
        raise RuntimeError(f"Backup file not created: {bak_file}")

    logger.info(f"Backup created: {bak_file} ({os.path.getsize(bak_file)} bytes)")
    return bak_file


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
