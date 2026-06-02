import logging
import os
import sys
import time

from dbshield_agent import __version__
from dbshield_agent.client import AgentClient
from dbshield_agent.config import load_config
from dbshield_agent.executor import execute_job


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
                ok = client.heartbeat(agent_version=__version__)
                if ok:
                    logger.debug("Heartbeat OK")
                else:
                    logger.warning("Heartbeat failed -- platform unreachable?")
                heartbeat_interval = config.poll_interval_seconds

            jobs = client.get_pending_jobs()
            if jobs:
                logger.info(f"Got {len(jobs)} pending job(s)")
                for job in jobs:
                    execute_job(job, config, client)
            else:
                logger.debug("No pending jobs")

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
