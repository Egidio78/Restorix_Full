from app.services.streamers.base import BaseStreamer
from app.services.streamers.s3 import S3Streamer
from app.services.streamers.sftp import SftpStreamer
from app.services.streamers.ftp import FtpStreamer
from app.services.streamers.webdav import WebdavStreamer

__all__ = ["BaseStreamer", "S3Streamer", "SftpStreamer", "FtpStreamer", "WebdavStreamer", "get_streamer"]


def get_streamer(storage_type: str, config: dict) -> BaseStreamer:
    """Factory for the right streamer based on storage type."""
    mapping = {
        "s3": S3Streamer,
        "sftp": SftpStreamer,
        "ftp": FtpStreamer,
        "webdav": WebdavStreamer,
    }
    cls = mapping.get(storage_type)
    if cls is None:
        raise ValueError(f"Unsupported storage type: {storage_type}")
    return cls(config)
