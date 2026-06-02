from abc import ABC, abstractmethod


class BaseUploader(ABC):
    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def upload(self, local_path: str, remote_name: str) -> str:
        ...
