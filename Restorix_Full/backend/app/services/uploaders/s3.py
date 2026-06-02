import boto3
from botocore.exceptions import ClientError

from app.services.uploaders.base import BaseUploader


class S3Uploader(BaseUploader):
    def __init__(self, config: dict):
        super().__init__(config)
        self.bucket = config["bucket"]
        self._client = boto3.client(
            "s3",
            endpoint_url=config.get("endpoint_url"),
            aws_access_key_id=config["access_key"],
            aws_secret_access_key=config["secret_key"],
            region_name=config.get("region", "us-east-1"),
        )

    def delete(self, remote_path: str) -> None:
        try:
            self._client.delete_object(Bucket=self.bucket, Key=remote_path)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404"):
                return  # gia' cancellato, ok
            raise

    def upload(self, local_path, remote_path: str) -> None:
        self._client.upload_file(str(local_path), self.bucket, remote_path)
