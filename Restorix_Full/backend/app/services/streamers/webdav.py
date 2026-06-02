import requests
from pathlib import Path
from urllib.parse import urljoin

from app.services.streamers.base import BaseStreamer


class WebdavStreamer(BaseStreamer):
    def _url(self, remote_path: str) -> str:
        return urljoin(self.config["base_url"].rstrip("/") + "/", remote_path.lstrip("/"))

    def head_size(self, remote_path: str) -> int:
        r = requests.head(
            self._url(remote_path),
            auth=(self.config["username"], self.config["password"]),
            timeout=30,
        )
        r.raise_for_status()
        return int(r.headers.get("Content-Length", 0))

    def download_to_file(self, remote_path: str, local_path: Path) -> None:
        with requests.get(
            self._url(remote_path),
            auth=(self.config["username"], self.config["password"]),
            stream=True,
            timeout=300,
        ) as r:
            r.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=4 * 1024 * 1024):
                    f.write(chunk)
