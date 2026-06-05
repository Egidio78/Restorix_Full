from __future__ import annotations
"""Whitelisted remote command handling for the agent.

Non-root actions (healthcheck, collect_logs, test_db, set_config) run directly in
the main agent process. Root actions (install_deps, restart_agent, repair) are
written to a trigger file consumed by the root runner (systemd path-unit); the
root runner reports their result.
"""
import json
import logging
import os
import shutil
import socket

logger = logging.getLogger(__name__)

RUNTIME_DIR = "/run/restorix-agent"
COMMAND_TRIGGER = os.path.join(RUNTIME_DIR, "command.json")

ROOT_ACTIONS = {"install_deps", "restart_agent", "repair"}


def _which(name: str) -> str | None:
    return shutil.which(name)


def _os_release() -> str:
    try:
        info = {}
        with open("/etc/os-release") as f:
            for line in f:
                if "=" in line:
                    k, v = line.rstrip().split("=", 1)
                    info[k] = v.strip('"')
        return f"{info.get('NAME', '?')} {info.get('VERSION_ID', '')}".strip()
    except Exception:
        return "unknown"


def _healthcheck(config) -> str:
    from dbshield_agent import __version__
    try:
        import pymysql  # noqa: F401
        pymysql_ok = True
    except Exception:
        pymysql_ok = False
    free_gb = None
    try:
        free_gb = round(shutil.disk_usage(config.temp_dir).free / (1024 ** 3), 1)
    except Exception:
        pass
    lines = [
        f"Agente: v{__version__}",
        f"Host: {socket.gethostname()}",
        f"OS: {_os_release()}",
        f"Python: {__import__('platform').python_version()}",
        f"mysqldump: {'OK (' + _which('mysqldump') + ')' if _which('mysqldump') else 'MANCANTE'}",
        f"mysql client: {'OK' if _which('mysql') else 'MANCANTE'}",
        f"pymysql: {'OK' if pymysql_ok else 'MANCANTE'}",
        f"sqlcmd: {'OK (' + _which('sqlcmd') + ')' if _which('sqlcmd') else 'MANCANTE'}",
        f"gzip: {'OK' if _which('gzip') else 'MANCANTE'}",
        f"Cartella temp: {config.temp_dir} (liberi: {free_gb} GB)" if free_gb is not None else f"Cartella temp: {config.temp_dir}",
        f"Poll interval: {config.poll_interval_seconds}s | Log level: {config.log_level}",
    ]
    return "\n".join(lines)


def _collect_logs(lines: int = 200) -> str:
    log_path = "/var/log/restorix-agent/agent.log"
    try:
        with open(log_path, "r", errors="replace") as f:
            data = f.readlines()
        return "".join(data[-lines:]) or "(log vuoto)"
    except FileNotFoundError:
        return f"Log non trovato: {log_path}"
    except Exception as e:
        return f"Errore lettura log: {e}"


def _test_db(config, params: dict, client) -> str:
    """Fetch credentials from the platform and try to connect."""
    db_id = params.get("db_instance_id")
    if not db_id:
        return "db_instance_id mancante"
    creds = client.get_db_credentials(db_id)
    if not creds:
        return "Impossibile ottenere le credenziali dalla piattaforma"
    engine = creds.get("engine", "mssql")
    conn = creds.get("connection_string", "")
    user = creds.get("username", "")
    pwd = creds.get("password", "")
    if engine == "mysql":
        from dbshield_agent.mysql_runner import discover_mysql_databases
        dbs, err = discover_mysql_databases(conn, user, pwd)
        if err:
            return f"Connessione MySQL FALLITA: {err}"
        return f"Connessione MySQL OK. {len(dbs)} database visibili."
    else:
        from dbshield_agent.discovery import discover_databases
        dbs, err = discover_databases(conn, user, pwd)
        if err:
            return f"Connessione MSSQL FALLITA: {err}"
        return f"Connessione MSSQL OK. {len(dbs)} database visibili."


def _set_config(config, params: dict) -> tuple[str, bool]:
    """Merge new values into config.json. Returns (message, needs_restart)."""
    config_path = os.environ.get("RESTORIX_CONFIG", "/etc/restorix-agent/config.json")
    try:
        with open(config_path) as f:
            data = json.load(f)
    except Exception as e:
        return (f"Impossibile leggere config: {e}", False)
    changed = []
    if "poll_interval_seconds" in params:
        data["poll_interval_seconds"] = int(params["poll_interval_seconds"]); changed.append("poll_interval_seconds")
    if "log_level" in params:
        data["log_level"] = str(params["log_level"]).upper(); changed.append("log_level")
    if "temp_dir" in params:
        data["temp_dir"] = str(params["temp_dir"]); changed.append("temp_dir")
    if not changed:
        return ("Nessun campo valido da aggiornare", False)
    try:
        tmp = config_path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, config_path)
    except Exception as e:
        return (f"Impossibile scrivere config: {e}", False)
    return (f"Config aggiornata: {', '.join(changed)}. Riavvio agente per applicare.", True)


def _queue_root_command(cmd: dict, logger) -> None:
    """Write the trigger consumed by the root runner; it reports the result."""
    try:
        os.makedirs(RUNTIME_DIR, exist_ok=True)
        tmp = COMMAND_TRIGGER + ".tmp"
        with open(tmp, "w") as f:
            json.dump(cmd, f)
        os.replace(tmp, COMMAND_TRIGGER)
        logger.info("Root command queued: %s (id=%s)", cmd.get("action"), cmd.get("id"))
    except Exception as e:
        logger.warning("Could not queue root command: %s", e)


def ensure_tool(tool: str, dep: str, logger, timeout: int = 180) -> bool:
    """If `tool` (e.g. mysqldump) is missing, ask the root runner to install `dep`
    and wait until it appears. Returns True if available, False on timeout."""
    import time
    if _which(tool):
        return True
    logger.info("%s missing — requesting auto-install of '%s'", tool, dep)
    _queue_root_command({"action": "install_deps", "params": {"deps": [dep]}}, logger)
    waited = 0
    while waited < timeout:
        time.sleep(5)
        waited += 5
        if _which(tool):
            logger.info("%s now available after %ds", tool, waited)
            return True
    logger.error("%s still missing after %ds", tool, timeout)
    return False


def handle_command(cmd: dict, config, client) -> bool:
    """Execute a command. Returns True if the agent should restart afterwards."""
    action = cmd.get("action")
    cmd_id = cmd.get("id")
    params = cmd.get("params") or {}
    logger.info("Handling command %s (%s)", action, cmd_id)

    if action in ROOT_ACTIONS:
        # Delegate to the root runner (it reports the result for this id).
        _queue_root_command({"id": cmd_id, "action": action, "params": params}, logger)
        return False

    try:
        if action == "healthcheck":
            client.report_command_result(cmd_id, True, _healthcheck(config))
        elif action == "collect_logs":
            client.report_command_result(cmd_id, True, _collect_logs(int(params.get("lines", 200))))
        elif action == "test_db":
            msg = _test_db(config, params, client)
            ok = "OK" in msg and "FALLITA" not in msg
            client.report_command_result(cmd_id, ok, msg)
        elif action == "set_config":
            msg, needs_restart = _set_config(config, params)
            client.report_command_result(cmd_id, "aggiornata" in msg.lower(), msg)
            return needs_restart
        else:
            client.report_command_result(cmd_id, False, f"Azione sconosciuta: {action}")
    except Exception as e:
        logger.error("Command %s failed: %s", action, e)
        try:
            client.report_command_result(cmd_id, False, f"Errore: {e}")
        except Exception:
            pass
    return False
