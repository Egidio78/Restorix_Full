import logging
from dbshield_agent.storage.base import BaseUploader

logger = logging.getLogger(__name__)


class SFTPUploader(BaseUploader):
    def upload(self, local_path: str, remote_name: str) -> str:
        import paramiko

        host = self.config["host"]
        port = int(self.config.get("port", 22))
        username = self.config.get("username", "")
        password = self.config.get("password", "")
        remote_dir = self.config.get("path", "/backups").rstrip("/")
        remote_path = f"{remote_dir}/{remote_name}"

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(host, port=port, username=username, password=password, timeout=30)
            sftp = client.open_sftp()
            try:
                sftp.stat(remote_dir)
            except FileNotFoundError:
                sftp.mkdir(remote_dir)
            sftp.put(local_path, remote_path)
            sftp.close()
            logger.info(f"SFTP upload complete: {remote_path}")
            return remote_path
        finally:
            client.close()
