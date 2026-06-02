from dbshield_agent.storage.base import BaseUploader
from dbshield_agent.storage.s3 import S3Uploader
from dbshield_agent.storage.sftp import SFTPUploader
from dbshield_agent.storage.ftp import FTPUploader
from dbshield_agent.storage.webdav import WebDAVUploader


def get_uploader(storage_type: str, config: dict) -> BaseUploader:
    uploaders = {
        "s3": S3Uploader,
        "sftp": SFTPUploader,
        "ftp": FTPUploader,
        "ftps": FTPUploader,
        "nextcloud": WebDAVUploader,
        "webdav": WebDAVUploader,
    }
    cls = uploaders.get(storage_type)
    if not cls:
        raise ValueError(f"Unsupported storage type: {storage_type}")
    return cls(config)
