import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.retention import RetentionService


@pytest.mark.asyncio
async def test_purge_run_success_marks_run_as_purged():
    run = MagicMock()
    run.id = "run-uuid"
    run.file_path = "backup/db-20260101.bak"
    run.retention_purge_attempts = 0
    run.job.storage_destination.storage_type.value = "s3"
    run.job.storage_destination.config_enc = "encrypted"

    fake_uploader = MagicMock()
    fake_uploader.delete = MagicMock(return_value=None)

    db = AsyncMock()

    with patch("app.services.retention.get_uploader", return_value=fake_uploader), \
         patch("app.services.retention.decrypt_storage_config", return_value={"bucket": "b", "access_key": "k", "secret_key": "s"}):
        service = RetentionService(db)
        result = await service.purge_run(run)

    assert result.success is True
    assert run.retention_purged is True
    assert run.retention_purged_at is not None
    fake_uploader.delete.assert_called_once_with("backup/db-20260101.bak")


@pytest.mark.asyncio
async def test_purge_run_failure_increments_attempts():
    run = MagicMock()
    run.id = "run-uuid"
    run.file_path = "backup/db.bak"
    run.retention_purge_attempts = 2
    run.retention_purged = False
    run.purge_abandoned = False
    run.job.storage_destination.storage_type.value = "s3"
    run.job.storage_destination.config_enc = "encrypted"

    fake_uploader = MagicMock()
    fake_uploader.delete = MagicMock(side_effect=RuntimeError("network unreachable"))

    db = AsyncMock()

    with patch("app.services.retention.get_uploader", return_value=fake_uploader), \
         patch("app.services.retention.decrypt_storage_config", return_value={"bucket": "b", "access_key": "k", "secret_key": "s"}):
        service = RetentionService(db)
        result = await service.purge_run(run)

    assert result.success is False
    assert "network unreachable" in result.error
    assert run.retention_purge_attempts == 3
    assert run.purge_abandoned is False
    assert run.retention_purged is False


@pytest.mark.asyncio
async def test_purge_run_abandons_after_5_attempts():
    run = MagicMock()
    run.id = "run-uuid"
    run.file_path = "backup/db.bak"
    run.retention_purge_attempts = 4
    run.job.storage_destination.storage_type.value = "s3"
    run.job.storage_destination.config_enc = "encrypted"

    fake_uploader = MagicMock()
    fake_uploader.delete = MagicMock(side_effect=RuntimeError("permission denied"))

    db = AsyncMock()

    with patch("app.services.retention.get_uploader", return_value=fake_uploader), \
         patch("app.services.retention.decrypt_storage_config", return_value={"bucket": "b", "access_key": "k", "secret_key": "s"}):
        service = RetentionService(db)
        await service.purge_run(run)

    assert run.retention_purge_attempts == 5
    assert run.purge_abandoned is True
