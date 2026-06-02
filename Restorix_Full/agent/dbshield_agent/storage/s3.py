import logging
import os
from dbshield_agent.storage.base import BaseUploader

logger = logging.getLogger(__name__)


class S3Uploader(BaseUploader):
    def upload(self, local_path: str, remote_name: str) -> str:
        import boto3
        from botocore.config import Config

        bucket = self.config["bucket"]
        region = self.config.get("region", "us-east-1")
        access_key = self.config.get("access_key")
        secret_key = self.config.get("secret_key")
        endpoint = self.config.get("endpoint")
        prefix = self.config.get("prefix", "dbshield/")

        kwargs = {"region_name": region, "config": Config(signature_version="s3v4")}
        if access_key and secret_key:
            kwargs["aws_access_key_id"] = access_key
            kwargs["aws_secret_access_key"] = secret_key
        if endpoint:
            kwargs["endpoint_url"] = endpoint

        s3 = boto3.client("s3", **kwargs)
        remote_key = f"{prefix}{remote_name}"
        logger.info(f"Uploading {os.path.getsize(local_path)} bytes to s3://{bucket}/{remote_key}")
        s3.upload_file(local_path, bucket, remote_key)
        logger.info(f"S3 upload complete: {remote_key}")
        return remote_key
