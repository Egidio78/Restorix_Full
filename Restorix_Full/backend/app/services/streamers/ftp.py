import ftplib
from pathlib import Path

from app.services.streamers.base import BaseStreamer


class FtpStreamer(BaseStreamer):
    def _connect(self):
        cls = ftplib.FTP_TLS if self.config.get("tls") else ftplib.FTP
        ftp = cls()
        ftp.connect(self.config["host"], int(self.config.get("port", 21)))
        ftp.login(self.config["username"], self.config["password"])
        if isinstance(ftp, ftplib.FTP_TLS):
            ftp.prot_p()
        return ftp

    def head_size(self, remote_path: str) -> int:
        ftp = self._connect()
        try:
            return ftp.size(remote_path) or 0
        finally:
            ftp.quit()

    def download_to_file(self, remote_path: str, local_path: Path) -> None:
        ftp = self._connect()
        try:
            with open(local_path, "wb") as f:
                ftp.retrbinary(f"RETR {remote_path}", f.write)
        finally:
            ftp.quit()
