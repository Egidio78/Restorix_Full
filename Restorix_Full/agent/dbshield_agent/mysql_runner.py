"""MySQL backup and discovery via mysql/mysqldump CLI."""
import logging
import os
import subprocess
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
    """Return list of user database names on the MySQL server."""
    host, port = _parse_host_port(connection_string)

    cmd = ["mysql", "-h", host, "-P", str(port), "--connect-timeout=10"]
    if username:
        cmd += ["-u", username, f"-p{password}"]
    cmd += ["--batch", "--skip-column-names", "-e", "SHOW DATABASES;"]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return [], f"mysql failed: {result.stderr.strip() or result.stdout.strip()}"
        databases = [
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip() and line.strip().lower() not in _SYSTEM_DBS
        ]
        return databases, None
    except FileNotFoundError:
        return [], "mysql client not installed on this server"
    except subprocess.TimeoutExpired:
        return [], "mysql discovery timed out (30s)"
    except Exception as e:
        return [], f"Discovery error: {e}"


def create_mysql_backup(
    connection_string: str,
    db_name: str,
    username: str,
    password: str,
    temp_dir: str,
) -> str:
    """Run mysqldump | gzip and return path to .sql.gz file."""
    host, port = _parse_host_port(connection_string)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_name = db_name.replace(" ", "_").replace("/", "_")
    out_path = os.path.join(temp_dir, f"{safe_name}_{timestamp}.sql.gz")

    dump_cmd = [
        "mysqldump",
        "-h", host,
        "-P", str(port),
        "--single-transaction",
        "--routines",
        "--triggers",
        "--connect-timeout=10",
    ]
    if username:
        dump_cmd += ["-u", username, f"-p{password}"]
    dump_cmd.append(db_name)

    gzip_cmd = ["gzip", "-c"]

    logger.info("Starting MySQL backup: %s/%s → %s", host, db_name, out_path)

    try:
        with open(out_path, "wb") as out_file:
            dump_proc = subprocess.Popen(
                dump_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            gzip_proc = subprocess.Popen(
                gzip_cmd,
                stdin=dump_proc.stdout,
                stdout=out_file,
                stderr=subprocess.PIPE,
            )
            dump_proc.stdout.close()  # allow dump_proc to receive SIGPIPE if gzip exits

            gzip_proc.wait(timeout=7200)  # 2 ore max
            dump_proc.wait(timeout=10)

        if dump_proc.returncode != 0:
            stderr = dump_proc.stderr.read().decode(errors="replace")
            raise RuntimeError(f"mysqldump failed (exit {dump_proc.returncode}): {stderr.strip()}")

        if gzip_proc.returncode != 0:
            raise RuntimeError(f"gzip failed (exit {gzip_proc.returncode})")

        size = os.path.getsize(out_path)
        logger.info("MySQL backup completed: %s (%.1f MB)", out_path, size / 1024 / 1024)
        return out_path

    except Exception:
        if os.path.exists(out_path):
            try:
                os.remove(out_path)
            except OSError:
                pass
        raise
