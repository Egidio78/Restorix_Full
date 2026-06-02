import logging
import os
import requests
from requests.auth import HTTPBasicAuth
from dbshield_agent.storage.base import BaseUploader

logger = logging.getLogger(__name__)


class WebDAVUploader(BaseUploader):
    def upload(self, local_path: str, remote_name: str) -> str:
        base_url = self.config["url"].rstrip("/")
        username = self.config.get("username", "")
        password = self.config.get("password", "")
        remote_url = f"{base_url}/{remote_name}"

        auth = HTTPBasicAuth(username, password) if username else None
        file_size = os.path.getsize(local_path)

        with open(local_path, "rb") as f:
            response = requests.put(
                remote_url,
                data=f,
                auth=auth,
                headers={"Content-Length": str(file_size)},
                timeout=300,
            )
        response.raise_for_status()
        logger.info(f"WebDAV upload complete: {remote_url}")
        return remote_url
