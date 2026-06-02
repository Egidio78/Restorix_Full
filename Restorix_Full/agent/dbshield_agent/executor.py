from __future__ import annotations
import logging
import os

from dbshield_agent.backup import create_backup, sha256_file
from dbshield_agent.folder_backup import create_folder_backup
from dbshield_agent.client import AgentClient
from dbshield_agent.config import AgentConfig
from dbshield_agent.crypto import compress_file, encrypt_file
from dbshield_agent.storage import get_uploader

logger = logging.getLogger(__name__)


def execute_job(job: dict, config: AgentConfig, client: AgentClient) -> None:
    run_id = job["run_id"]
    backup_type = job.get("backup_type", "mssql")
    backup_file = None

    try:
        if backup_type == "folder":
            folder = job.get("folder_path")
            if not folder:
                raise RuntimeError("folder_path missing for folder backup")
            backup_file = create_folder_backup(folder, config.temp_dir, job.get("job_name", "folder"))
            already_compressed = True

        elif backup_type == "mysql":
            from dbshield_agent.mysql_runner import create_mysql_backup
            connection_string = job.get("connection_string", "")
            if not connection_string:
                raise RuntimeError("connection_string missing for MySQL backup")
            backup_file = create_mysql_backup(
                connection_string=connection_string,
                db_name=job["db_name"],
                username=job.get("db_username", ""),
                password=job.get("db_password", ""),
                temp_dir=config.temp_dir,
            )
            already_compressed = True  # sempre .sql.gz

        else:
            # mssql (default)
            native = job.get("mssql_native_compression", False)
            backup_file = create_backup(
                mssql_instance=job.get("connection_string") or job.get("mssql_instance", ""),
                db_name=job["db_name"],
                username=job.get("db_username", ""),
                password=job.get("db_password", ""),
                temp_dir=config.temp_dir,
                native_compression=native,
            )
            already_compressed = native

        if job.get("compression_enabled") and not already_compressed:
            backup_file = compress_file(backup_file)

        if job.get("encryption_enabled") and job.get("encryption_password"):
            backup_file = encrypt_file(backup_file, job["encryption_password"])

        checksum = sha256_file(backup_file)
        size_bytes = os.path.getsize(backup_file)
        remote_name = os.path.basename(backup_file)

        uploader = get_uploader(job["storage_type"], job["storage_config"])
        remote_path = uploader.upload(backup_file, remote_name)

        client.report_success(run_id=run_id, size_bytes=size_bytes, file_path=remote_path, checksum=checksum)
        logger.info(f"Job {run_id} completed successfully: {remote_path}")

    except Exception as e:
        logger.error(f"Job {run_id} failed: {e}")
        client.report_failure(run_id=run_id, error_message=str(e))

    finally:
        if backup_file and os.path.exists(backup_file):
            try:
                os.remove(backup_file)
            except Exception:
                pass
