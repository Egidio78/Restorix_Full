import boto3
import pytest
from moto import mock_aws

from app.services.uploaders import get_uploader


@mock_aws
def test_s3_delete_removes_object():
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-bucket")
    s3.put_object(Bucket="test-bucket", Key="backup/db.bak", Body=b"data")

    uploader = get_uploader("s3", {
        "bucket": "test-bucket",
        "access_key": "fake",
        "secret_key": "fake",
        "region": "us-east-1",
    })
    uploader.delete("backup/db.bak")

    resp = s3.list_objects_v2(Bucket="test-bucket")
    assert resp.get("KeyCount", 0) == 0


@mock_aws
def test_s3_delete_missing_key_is_idempotent():
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-bucket")

    uploader = get_uploader("s3", {
        "bucket": "test-bucket",
        "access_key": "fake",
        "secret_key": "fake",
        "region": "us-east-1",
    })
    # Non deve sollevare
    uploader.delete("backup/missing.bak")


def test_unknown_storage_type_raises():
    with pytest.raises(ValueError, match="Unsupported storage type"):
        get_uploader("dropbox", {})
