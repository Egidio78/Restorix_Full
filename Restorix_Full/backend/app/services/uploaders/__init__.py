from app.services.uploaders.base import BaseUploader, UploadResult
from app.services.uploaders.s3 import S3Uploader
from app.services.uploaders.sftp import SftpUploader
from app.services.uploaders.ftp import FtpUploader
from app.services.uploaders.webdav import WebdavUploader

__all__ = [
    "BaseUploader",
    "UploadResult",
    "S3Uploader",
    "SftpUploader",
    "FtpUploader",
    "WebdavUploader",
    "get_uploader",
]


def get_uploader(storage_type: str, config: dict) -> BaseUploader:
    """Factory che istanzia l'uploader giusto in base al tipo di storage."""
    mapping = {
        "s3": S3Uploader,
        "sftp": SftpUploader,
        "ftp": FtpUploader,
        "webdav": WebdavUploader,
    }
    cls = mapping.get(storage_type)
    if cls is None:
        raise ValueError(f"Unsupported storage type: {storage_type}")
    return cls(config)
