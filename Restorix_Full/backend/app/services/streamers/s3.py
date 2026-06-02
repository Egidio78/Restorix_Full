import boto3
from botocore.config import Config
from pathlib import Path

from app.services.streamers.base import BaseStreamer


class S3Streamer(BaseStreamer):
    def __init__(self, config: dict):
        super().__init__(config)
        self.bucket = config["bucket"]
        # Accept both 'endpoint' and 'endpoint_url' keys — keep as-is (no stripping)
        endpoint_url = config.get("endpoint_url") or config.get("endpoint")
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=config["access_key"],
            aws_secret_access_key=config["secret_key"],
            region_name=config.get("region", "us-east-1"),
            config=Config(signature_version="s3v4"),
        )

    def head_size(self, remote_path: str) -> int:
        resp = self._client.head_object(Bucket=self.bucket, Key=remote_path)
        return int(resp["ContentLength"])

    def download_to_file(self, remote_path: str, local_path: Path) -> None:
        self._client.download_file(self.bucket, remote_path, str(local_path))

    def generate_presigned_url(self, remote_path: str, ttl_seconds: int = 900) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": remote_path},
            ExpiresIn=ttl_seconds,
        )
