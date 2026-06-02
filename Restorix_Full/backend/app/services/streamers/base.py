from abc import ABC, abstractmethod
from pathlib import Path


class BaseStreamer(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def head_size(self, remote_path: str) -> int:
        """Return the size of the remote file in bytes."""

    @abstractmethod
    def download_to_file(self, remote_path: str, local_path: Path) -> None:
        """Download the remote file to the local path."""
