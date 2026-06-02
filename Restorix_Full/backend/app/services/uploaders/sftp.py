import paramiko

from app.services.uploaders.base import BaseUploader


class SftpUploader(BaseUploader):
    def _connect(self):
        transport = paramiko.Transport((self.config["host"], int(self.config.get("port", 22))))
        transport.connect(username=self.config["username"], password=self.config["password"])
        return paramiko.SFTPClient.from_transport(transport), transport

    def delete(self, remote_path: str) -> None:
        sftp, transport = self._connect()
        try:
            try:
                sftp.remove(remote_path)
            except FileNotFoundError:
                pass  # idempotente
        finally:
            sftp.close()
            transport.close()

    def upload(self, local_path, remote_path: str) -> None:
        sftp, transport = self._connect()
        try:
            # Assicura che la dir parent esista (mkdir step-by-step)
            parts = remote_path.split("/")
            parent_parts = parts[:-1]
            absolute = remote_path.startswith("/")
            cur = ""
            for p in parent_parts:
                if not p:
                    continue
                if cur:
                    cur = cur + "/" + p
                else:
                    cur = ("/" + p) if absolute else p
                try:
                    sftp.mkdir(cur)
                except IOError:
                    pass  # esiste gia'
            sftp.put(str(local_path), remote_path)
        finally:
            sftp.close()
            transport.close()
