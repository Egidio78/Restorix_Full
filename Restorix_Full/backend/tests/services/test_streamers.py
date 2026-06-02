import pytest
import boto3
from moto import mock_aws
from pathlib import Path

from app.services.streamers import get_streamer


@mock_aws
def test_s3_streamer_head_and_download(tmp_path):
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-bucket")
    payload = b"x" * (5 * 1024 * 1024)  # 5 MiB
    s3.put_object(Bucket="test-bucket", Key="backup/db.bak", Body=payload)

    streamer = get_streamer("s3", {
        "bucket": "test-bucket",
        "access_key": "fake",
        "secret_key": "fake",
        "region": "us-east-1",
    })

    assert streamer.head_size("backup/db.bak") == len(payload)

    dest = tmp_path / "downloaded.bak"
    streamer.download_to_file("backup/db.bak", dest)
    assert dest.read_bytes() == payload


@mock_aws
def test_s3_presigned_url():
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-bucket")
    s3.put_object(Bucket="test-bucket", Key="backup/db.bak", Body=b"data")

    streamer = get_streamer("s3", {
        "bucket": "test-bucket",
        "access_key": "fake",
        "secret_key": "fake",
        "region": "us-east-1",
    })
    url = streamer.generate_presigned_url("backup/db.bak", ttl_seconds=300)
    assert "test-bucket" in url
    assert "backup/db.bak" in url
    assert "X-Amz-Expires=300" in url


def test_get_streamer_unknown_type_raises():
    with pytest.raises(ValueError, match="Unsupported storage type"):
        get_streamer("dropbox", {})
