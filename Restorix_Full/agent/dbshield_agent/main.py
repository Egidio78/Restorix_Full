from __future__ import annotations
import logging
import os
import sys
import time

from dbshield_agent import __version__
from dbshield_agent.client import AgentClient
from dbshield_agent.config import load_config
from dbshield_agent.executor import execute_job

# Trigger file written for the root updater (watched by a systemd path-unit).
UPDATE_TRIGGER_DIR = "/run/restorix-agent"
UPDATE_TRIGGER_FILE = os.path.join(UPDATE_TRIGGER_DIR, "update.json")


def _request_self_update(update: dict, logger) -> None:
    """Write the update instruction for the root updater. The non-root agent can't
    restart its own systemd service, so a root path-unit consumes this file."""
    import json
    if not update.get("download_url") or not update.get("sha256"):
        return
    if os.path.exists(UPDATE_TRIGGER_FILE):
        return  # an update is already queued
    try:
        os.makedirs(UPDATE_TRIGGER_DIR, exist_ok=True)
        tmp = UPDATE_TRIGGER_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(update, f)
        os.replace(tmp, UPDATE_TRIGGER_FILE)
        logger.info("Self-update queued: v%s", update.get("version"))
    except Exception as e:
        logger.warning("Could not queue self-update: %s", e)


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main() -> None:
    config_path = os.environ.get("RESTORIX_CONFIG", "/etc/restorix-agent/config.json")
    config = load_config(config_path)
    setup_logging(config.log_level)

    logger = logging.getLogger("dbshield_agent")
    logger.info(f"DBShield Agent v{__version__} starting")
    logger.info(f"Platform: {config.api_url}")

    os.makedirs(config.temp_dir, exist_ok=True)
    client = AgentClient(config)
    heartbeat_interval = 0

    while True:
        try:
            if heartbeat_interval <= 0:
                hb = client.heartbeat(agent_version=__version__)
                if hb is not None:
                    logger.debug("Heartbeat OK")
                    update = hb.get("update") if isinstance(hb, dict) else None
                    if update:
                        _request_self_update(update, logger)
                else:
                    logger.warning("Heartbeat failed -- platform unreachable?")
                heartbeat_interval = config.poll_interval_seconds

            jobs = client.get_pending_jobs()
            if jobs:
                logger.info(f"Got {len(jobs)} pending job(s)")
                for job in jobs:
                    try:
                        execute_job(job, config, client)
                    except Exception as e:
                        logger.error(f"Unhandled error processing job: {e}")
            else:
                logger.debug("No pending jobs")

            # Check for a pending management command
            cmd = client.get_command()
            if cmd:
                from dbshield_agent.commands import handle_command
                needs_restart = handle_command(cmd, config, client)
                if needs_restart:
                    logger.info("Config changed — exiting so systemd restarts with new config")
                    sys.exit(0)

            # Check for discovery request
            discovery_req = client.get_discovery_request()
            if discovery_req:
                engine = discovery_req.get("engine", "mssql")
                connection_string = discovery_req.get("connection_string", "") or discovery_req.get("mssql_instance", "")
                username = discovery_req.get("username", "")
                password = discovery_req.get("password", "")

                if engine == "mysql":
                    from dbshield_agent.mysql_runner import discover_mysql_databases
                    logger.info(f"MySQL discovery request for {connection_string}")
                    dbs, err = discover_mysql_databases(connection_string, username, password)
                else:
                    from dbshield_agent.discovery import discover_databases
                    logger.info(f"MSSQL discovery request for {connection_string}")
                    dbs, err = discover_databases(connection_string, username, password)

                if err:
                    logger.error(f"Discovery failed: {err}")
                else:
                    logger.info(f"Discovered {len(dbs)} databases: {dbs}")
                client.report_discovery(dbs, err)

        except KeyboardInterrupt:
            logger.info("Agent stopped by user")
            sys.exit(0)
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")

        time.sleep(config.poll_interval_seconds)
        heartbeat_interval -= config.poll_interval_seconds


if __name__ == "__main__":
    main()
