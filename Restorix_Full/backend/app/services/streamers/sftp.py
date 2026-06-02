import paramiko
from pathlib import Path

from app.services.streamers.base import BaseStreamer


class SftpStreamer(BaseStreamer):
    def _connect(self):
        transport = paramiko.Transport((self.config["host"], int(self.config.get("port", 22))))
        transport.connect(username=self.config["username"], password=self.config["password"])
        return paramiko.SFTPClient.from_transport(transport), transport

    def head_size(self, remote_path: str) -> int:
        sftp, transport = self._connect()
        try:
            return sftp.stat(remote_path).st_size
        finally:
            sftp.close()
            transport.close()

    def download_to_file(self, remote_path: str, local_path: Path) -> None:
        sftp, transport = self._connect()
        try:
            sftp.get(remote_path, str(local_path))
        finally:
            sftp.close()
            transport.close()
