from __future__ import annotations
"""MySQL backup and discovery via mysql/mysqldump CLI."""
import fnmatch
import logging
import os
import subprocess
import threading
import time
from datetime import datetime

logger = logging.getLogger(__name__)

_SYSTEM_DBS = {"information_schema", "performance_schema", "mysql", "sys"}


def _list_tables(host: int, port: int, db_name: str, username: str, password: str) -> list[str]:
    """Return all base table names in db_name (via pymysql)."""
    import pymysql  # type: ignore
    conn = pymysql.connect(
        host=host, port=port, user=username or "root", password=password or "",
        database=db_name, connect_timeout=10,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'")
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def _resolve_excluded_tables(host, port, db_name, username, password, patterns: str) -> list[str]:
    """Expand comma-separated glob patterns (e.g. 'vte_rep_subq_*, *_tmp') into the
    concrete table names that currently exist and match."""
    pats = [p.strip() for p in (patterns or "").split(",") if p.strip()]
    if not pats:
        return []
    try:
        tables = _list_tables(host, port, db_name, username, password)
    except Exception as e:
        logger.warning("Could not list tables to apply exclude patterns: %s", e)
        return []
    excluded = [t for t in tables if any(fnmatch.fnmatch(t, p) for p in pats)]
    if excluded:
        logger.info("Excluding %d tables matching %s", len(excluded), pats)
    return excluded


def _parse_host_port(connection_string: str) -> tuple[str, int]:
    """Parse 'host:port' → (host, port). Default port: 3306."""
    if ":" in connection_string:
        host, port_str = connection_string.rsplit(":", 1)
        try:
            return host.strip(), int(port_str.strip())
        except ValueError:
            pass
    return connection_string.strip(), 3306


def discover_mysql_databases(connection_string: str, username: str, password: str) -> tuple[list[str], str | None]:
    """Return list of user database names using pymysql (no CLI dependency)."""
    host, port = _parse_host_port(connection_string)
    try:
        import pymysql  # type: ignore
        conn = pymysql.connect(
            host=host, port=port,
            user=username or "root",
            password=password or "",
            connect_timeout=10,
        )
        with conn:
            with conn.cursor() as cur:
                cur.execute("SHOW DATABASES")
                databases = [
                    row[0] for row in cur.fetchall()
                    if row[0].lower() not in _SYSTEM_DBS
                ]
        return databases, None
    except ImportError:
        return [], "pymysql not installed — run: pip install pymysql"
    except Exception as e:
        return [], f"Discovery error: {e}"


def create_mysql_backup(
    connection_string: str,
    db_name: str,
    username: str,
    password: str,
    temp_dir: str,
    name_prefix: str = "",
    exclude_tables: str = "",
) -> str:
    """Run mysqldump | gzip and return path to .sql.gz file.

    exclude_tables: comma-separated glob patterns (e.g. 'vte_rep_subq_*') — matching
    tables are skipped via --ignore-table. Useful for volatile CRM temp/report
    tables that cause 'Error 1412: Table definition has changed'.
    """
    host, port = _parse_host_port(connection_string)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # ora locale del server (Europe/Rome)
    safe_name = db_name.replace(" ", "_").replace("/", "_")
    base = f"{name_prefix}_{safe_name}" if name_prefix else safe_name
    out_path = os.path.join(temp_dir, f"{base}_{timestamp}.sql.gz")

    excluded = _resolve_excluded_tables(host, port, db_name, username, password, exclude_tables)

    base_cmd = [
        "mysqldump",
        "-h", host,
        "-P", str(port),
        "--single-transaction",
        "--quick",
        "--routines",
        "--triggers",
    ]
    for tbl in excluded:
        base_cmd += [f"--ignore-table={db_name}.{tbl}"]
    if username:
        base_cmd += ["-u", username]
    dump_cmd = base_cmd + [db_name]

    # Pass MySQL password via env var (MYSQL_PWD) instead of argv to avoid
    # exposing it in `ps aux`.
    env = os.environ.copy()
    if password:
        env["MYSQL_PWD"] = password

    def _attempt() -> None:
        with open(out_path, "wb") as out_file:
            dump_proc = subprocess.Popen(dump_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            gzip_proc = subprocess.Popen(["gzip", "-c"], stdin=dump_proc.stdout, stdout=out_file, stderr=subprocess.PIPE)
            dump_proc.stdout.close()
            stderr_box = []

            def _drain():
                try:
                    stderr_box.append(dump_proc.stderr.read())
                except Exception:
                    stderr_box.append(b"")

            _t = threading.Thread(target=_drain, daemon=True)
            _t.start()
            gzip_proc.wait(timeout=7200)
            dump_proc.wait(timeout=10)
            _t.join(timeout=5)

        if dump_proc.returncode != 0:
            stderr = (stderr_box[0] if stderr_box else b"").decode(errors="replace")
            raise RuntimeError(f"mysqldump failed (exit {dump_proc.returncode}): {stderr.strip()}")
        if gzip_proc.returncode != 0:
            raise RuntimeError(f"gzip failed (exit {gzip_proc.returncode})")
        if os.path.getsize(out_path) == 0:
            raise RuntimeError("MySQL backup file is empty (0 bytes) — backup failed")

    logger.info("Starting MySQL backup: %s/%s → %s", host, db_name, out_path)
    # Retry on transient "table definition changed" (1412) — volatile temp tables.
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        try:
            _attempt()
            size = os.path.getsize(out_path)
            logger.info("MySQL backup completed: %s (%.1f MB)", out_path, size / 1024 / 1024)
            return out_path
        except Exception as e:
            msg = str(e)
            transient = "1412" in msg or "Table definition has changed" in msg
            if os.path.exists(out_path):
                try:
                    os.remove(out_path)
                except OSError:
                    pass
            if transient and attempt < max_attempts:
                logger.warning("Transient mysqldump error (attempt %d/%d), retrying: %s",
                               attempt, max_attempts, msg)
                time.sleep(3)
                continue
            raise
