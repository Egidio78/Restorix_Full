from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class UploadResult:
    remote_path: str
    bytes: int


class BaseUploader(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def delete(self, remote_path: str) -> None:
        """Cancella un oggetto remoto. Solleva eccezione se fallisce.

        404/Not Found NON e' errore: e' successo idempotente.
        """
        raise NotImplementedError

    @abstractmethod
    def upload(self, local_path, remote_path: str) -> None:
        """Carica il file locale su remote_path. Solleva eccezione su errore."""
        raise NotImplementedError
