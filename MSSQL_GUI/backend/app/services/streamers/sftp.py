import socket as _socket

import paramiko
from pathlib import Path

from app.core.paths import normalize_remote_path
from app.services.streamers.base import BaseStreamer


class SftpStreamer(BaseStreamer):
    def _connect(self):
        host = self.config["host"]
        port = int(self.config.get("port", 22))
        sock = _socket.create_connection((host, port), timeout=30)
        transport = paramiko.Transport(sock)
        transport.banner_timeout = 30
        transport.connect(username=self.config["username"], password=self.config["password"])
        return paramiko.SFTPClient.from_transport(transport), transport

    def head_size(self, remote_path: str) -> int:
        remote_path = normalize_remote_path(remote_path)
        sftp, transport = self._connect()
        try:
            return sftp.stat(remote_path).st_size
        finally:
            sftp.close()
            transport.close()

    def download_to_file(self, remote_path: str, local_path: Path) -> None:
        remote_path = normalize_remote_path(remote_path)
        sftp, transport = self._connect()
        try:
            sftp.get(remote_path, str(local_path))
        finally:
            sftp.close()
            transport.close()
