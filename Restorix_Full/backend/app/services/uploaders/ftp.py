import ftplib

from app.services.uploaders.base import BaseUploader


class FtpUploader(BaseUploader):
    def _connect(self):
        cls = ftplib.FTP_TLS if self.config.get("tls") else ftplib.FTP
        ftp = cls()
        ftp.connect(self.config["host"], int(self.config.get("port", 21)))
        ftp.login(self.config["username"], self.config["password"])
        if isinstance(ftp, ftplib.FTP_TLS):
            ftp.prot_p()
        return ftp

    def delete(self, remote_path: str) -> None:
        ftp = self._connect()
        try:
            try:
                ftp.delete(remote_path)
            except ftplib.error_perm as e:
                if "550" in str(e):  # file not found
                    return
                raise
        finally:
            ftp.quit()

    def upload(self, local_path, remote_path: str) -> None:
        ftp = self._connect()
        try:
            with open(local_path, "rb") as f:
                ftp.storbinary(f"STOR {remote_path}", f)
        finally:
            ftp.quit()
