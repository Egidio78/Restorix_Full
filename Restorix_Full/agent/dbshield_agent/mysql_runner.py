from __future__ import annotations
"""MySQL backup and discovery via mysql/mysqldump CLI."""
import logging
import os
import subprocess
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

_SYSTEM_DBS = {"information_schema", "performance_schema", "mysql", "sys"}


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
) -> str:
    """Run mysqldump | gzip and return path to .sql.gz file."""
    host, port = _parse_host_port(connection_string)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # ora locale del server (Europe/Rome)
    safe_name = db_name.replace(" ", "_").replace("/", "_")
    base = f"{name_prefix}_{safe_name}" if name_prefix else safe_name
    out_path = os.path.join(temp_dir, f"{base}_{timestamp}.sql.gz")

    dump_cmd = [
        "mysqldump",
        "-h", host,
        "-P", str(port),
        "--single-transaction",
        "--routines",
        "--triggers",
    ]
    if username:
        dump_cmd += ["-u", username]
    dump_cmd.append(db_name)

    gzip_cmd = ["gzip", "-c"]

    # Pass MySQL password via env var (MYSQL_PWD) instead of argv to avoid
    # exposing it in `ps aux`.
    env = os.environ.copy()
    if password:
        env["MYSQL_PWD"] = password

    logger.info("Starting MySQL backup: %s/%s → %s", host, db_name, out_path)

    try:
        with open(out_path, "wb") as out_file:
            dump_proc = subprocess.Popen(
                dump_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
            gzip_proc = subprocess.Popen(
                gzip_cmd,
                stdin=dump_proc.stdout,
                stdout=out_file,
                stderr=subprocess.PIPE,
            )
            dump_proc.stdout.close()  # allow dump_proc to receive SIGPIPE if gzip exits

            # Drain mysqldump stderr in a separate thread to avoid pipe deadlock
            # when many warnings fill the PIPE buffer.
            stderr_box = []

            def _drain():
                try:
                    stderr_box.append(dump_proc.stderr.read())
                except Exception:
                    stderr_box.append(b"")

            _t = threading.Thread(target=_drain, daemon=True)
            _t.start()

            gzip_proc.wait(timeout=7200)  # 2 ore max
            dump_proc.wait(timeout=10)
            _t.join(timeout=5)

        if dump_proc.returncode != 0:
            stderr = (stderr_box[0] if stderr_box else b"").decode(errors="replace")
            raise RuntimeError(f"mysqldump failed (exit {dump_proc.returncode}): {stderr.strip()}")

        if gzip_proc.returncode != 0:
            raise RuntimeError(f"gzip failed (exit {gzip_proc.returncode})")

        size = os.path.getsize(out_path)
        if size == 0:
            raise RuntimeError("MySQL backup file is empty (0 bytes) — backup failed")
        logger.info("MySQL backup completed: %s (%.1f MB)", out_path, size / 1024 / 1024)
        return out_path

    except Exception:
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except OSError:
                pass
        raise
