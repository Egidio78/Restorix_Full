from urllib.parse import urljoin

import requests

from app.services.uploaders.base import BaseUploader


class WebdavUploader(BaseUploader):
    def _url(self, remote_path: str) -> str:
        return urljoin(self.config["base_url"].rstrip("/") + "/", remote_path.lstrip("/"))

    def delete(self, remote_path: str) -> None:
        url = self._url(remote_path)
        resp = requests.delete(
            url,
            auth=(self.config["username"], self.config["password"]),
            timeout=30,
        )
        if resp.status_code in (204, 200, 404):
            return
        resp.raise_for_status()

    def upload(self, local_path, remote_path: str) -> None:
        url = self._url(remote_path)
        with open(local_path, "rb") as f:
            resp = requests.put(
                url,
                data=f,
                auth=(self.config["username"], self.config["password"]),
                timeout=300,
            )
        resp.raise_for_status()
