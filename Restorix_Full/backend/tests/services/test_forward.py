import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_forward_copy_does_not_delete_source(tmp_path):
    from app.services.forward import ForwardService

    src_run = MagicMock()
    src_run.file_path = "backups/db.bak.gz"
    src_run.job.storage_destination.config_enc = "encrypted_src"
    src_run.job.storage_destination.storage_type.value = "s3"
    src_run.job.organization.restore_temp_dir = str(tmp_path)
    src_run.forwarded_to_run_id = None

    target_storage = MagicMock()
    target_storage.config_enc = "encrypted_target"
    target_storage.storage_type.value = "s3"

    shadow_run = MagicMock()
    shadow_run.id = "shadow-id"

    streamer = MagicMock()
    def fake_download(remote, local):
        Path(local).write_bytes(b"x" * 1024)
    streamer.download_to_file = MagicMock(side_effect=fake_download)
    uploader = MagicMock()
    src_uploader = MagicMock()

    db = AsyncMock()
    with patch("app.services.forward.get_streamer", return_value=streamer), \
         patch("app.services.forward.get_uploader", side_effect=[uploader, src_uploader]), \
         patch("app.services.forward.decrypt_str", return_value='{"bucket":"b","access_key":"k","secret_key":"s"}'):
        svc = ForwardService(db)
        res = await svc.forward_run(src_run, target_storage, "copy", shadow_run)

    src_uploader.delete.assert_not_called()
    assert res["source_deleted"] is False
    assert shadow_run.status == "success"
    assert res["target_remote_path"].startswith("forwarded/")


@pytest.mark.asyncio
async def test_forward_move_deletes_source_and_sets_forwarded_to(tmp_path):
    from app.services.forward import ForwardService

    src_run = MagicMock()
    src_run.file_path = "backups/db.bak.gz"
    src_run.job.storage_destination.config_enc = "encrypted_src"
    src_run.job.storage_destination.storage_type.value = "s3"
    src_run.job.organization.restore_temp_dir = str(tmp_path)
    src_run.forwarded_to_run_id = None

    target_storage = MagicMock()
    target_storage.config_enc = "encrypted_target"
    target_storage.storage_type.value = "s3"

    shadow_run = MagicMock()
    shadow_run.id = "shadow-id"

    streamer = MagicMock()
    def fake_download(remote, local):
        Path(local).write_bytes(b"data")
    streamer.download_to_file = MagicMock(side_effect=fake_download)
    uploader = MagicMock()
    src_uploader = MagicMock()

    db = AsyncMock()
    with patch("app.services.forward.get_streamer", return_value=streamer), \
         patch("app.services.forward.get_uploader", side_effect=[uploader, src_uploader]), \
         patch("app.services.forward.decrypt_str", return_value='{"bucket":"b","access_key":"k","secret_key":"s"}'):
        svc = ForwardService(db)
        res = await svc.forward_run(src_run, target_storage, "move", shadow_run)

    src_uploader.delete.assert_called_once_with("backups/db.bak.gz")
    assert res["source_deleted"] is True
    assert src_run.forwarded_to_run_id == "shadow-id"
    assert shadow_run.status == "success"
    assert res["target_remote_path"] == "backups/db.bak.gz"


@pytest.mark.asyncio
async def test_forward_upload_failure_does_not_delete_source(tmp_path):
    from app.services.forward import ForwardService

    src_run = MagicMock()
    src_run.file_path = "backups/db.bak.gz"
    src_run.job.storage_destination.config_enc = "x"
    src_run.job.storage_destination.storage_type.value = "s3"
    src_run.job.organization.restore_temp_dir = str(tmp_path)
    src_run.forwarded_to_run_id = None

    target_storage = MagicMock()
    target_storage.config_enc = "y"
    target_storage.storage_type.value = "s3"

    shadow_run = MagicMock()
    shadow_run.id = "sid"

    streamer = MagicMock()
    def fake_download(r, l):
        Path(l).write_bytes(b"data")
    streamer.download_to_file = MagicMock(side_effect=fake_download)
    uploader = MagicMock()
    uploader.upload = MagicMock(side_effect=RuntimeError("upload failed"))
    src_uploader = MagicMock()

    db = AsyncMock()
    with patch("app.services.forward.get_streamer", return_value=streamer), \
         patch("app.services.forward.get_uploader", side_effect=[uploader, src_uploader]), \
         patch("app.services.forward.decrypt_str", return_value='{"bucket":"b","access_key":"k","secret_key":"s"}'):
        svc = ForwardService(db)
        with pytest.raises(RuntimeError, match="upload failed"):
            await svc.forward_run(src_run, target_storage, "move", shadow_run)

    src_uploader.delete.assert_not_called()
    assert shadow_run.status == "failed"
