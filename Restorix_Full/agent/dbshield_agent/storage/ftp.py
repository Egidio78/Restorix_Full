import ftplib
import logging
import ssl
from dbshield_agent.storage.base import BaseUploader

logger = logging.getLogger(__name__)


class FTPUploader(BaseUploader):
    def upload(self, local_path: str, remote_name: str) -> str:
        host = self.config["host"]
        port = int(self.config.get("port", 21))
        username = self.config.get("username", "")
        password = self.config.get("password", "")
        remote_dir = self.config.get("path", "/backups").rstrip("/")

        use_tls = self.config.get("use_tls", False)
        if use_tls:
            ftp = ftplib.FTP_TLS(context=ssl.create_default_context())
        else:
            ftp = ftplib.FTP()

        try:
            ftp.connect(host, port, timeout=30)
            ftp.login(username, password)
            if use_tls:
                ftp.prot_p()
            try:
                ftp.cwd(remote_dir)
            except ftplib.error_perm:
                ftp.mkd(remote_dir)
                ftp.cwd(remote_dir)
            remote_path = f"{remote_dir}/{remote_name}"
            with open(local_path, "rb") as f:
                ftp.storbinary(f"STOR {remote_name}", f)
            logger.info(f"FTP upload complete: {remote_path}")
            return remote_path
        finally:
            try:
                ftp.quit()
            except Exception:
                pass
