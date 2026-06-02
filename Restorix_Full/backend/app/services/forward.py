"""Storage-to-storage forward service.

Downloads a backup file from one storage destination and uploads it to another,
optionally deleting the source after successful upload (mode='move').
"""
import json as _json
import logging
import uuid as uuid_lib
from datetime import datetime
from pathlib import Path
from time import perf_counter

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt as decrypt_str
from app.services.streamers import get_streamer
from app.services.uploaders import get_uploader

logger = logging.getLogger(__name__)


class ForwardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def forward_run(
        self,
        source_run,
        target_storage,
        mode: str,
        shadow_run,
    ) -> dict:
        """Execute forward operation. Updates shadow_run in place.

        Returns dict {bytes, duration_seconds, source_deleted, target_remote_path}.
        On exception, marks shadow_run as 'failed' before re-raising.
        """
        if mode not in ("copy", "move"):
            raise ValueError(f"Invalid mode: {mode}")

        # Decrypt configs
        source_config = _json.loads(decrypt_str(source_run.job.storage_destination.config_enc))
        target_config = _json.loads(decrypt_str(target_storage.config_enc))

        source_type = source_run.job.storage_destination.storage_type
        source_type_str = source_type.value if hasattr(source_type, "value") else source_type
        target_type = target_storage.storage_type
        target_type_str = target_type.value if hasattr(target_type, "value") else target_type

        streamer = get_streamer(source_type_str, source_config)
        uploader = get_uploader(target_type_str, target_config)

        # Temp file under org's restore_temp_dir
        org = source_run.job.organization
        temp_base = Path(org.restore_temp_dir or "/var/lib/dbshield/restore-tmp")
        temp_base.mkdir(parents=True, exist_ok=True)
        temp_file = temp_base / f"forward-{uuid_lib.uuid4().hex}.tmp"

        source_remote_path = source_run.file_path
        target_remote_path = f"forwarded/{Path(source_remote_path).name}" if mode == "copy" else source_remote_path

        t0 = perf_counter()
        try:
            # Download
            streamer.download_to_file(source_remote_path, temp_file)
            size_bytes = temp_file.stat().st_size

            # Upload
            uploader.upload(temp_file, target_remote_path)

            # On move: delete source AFTER upload OK
            source_deleted = False
            if mode == "move":
                source_uploader = get_uploader(source_type_str, source_config)
                source_uploader.delete(source_remote_path)
                source_deleted = True

            # Mark shadow_run as success
            shadow_run.status = "success"
            shadow_run.finished_at = datetime.utcnow()
            shadow_run.size_bytes = size_bytes
            shadow_run.file_path = target_remote_path

            # On move: update source.forwarded_to_run_id
            if mode == "move":
                source_run.forwarded_to_run_id = shadow_run.id

            await self.db.commit()
            return {
                "bytes": size_bytes,
                "duration_seconds": round(perf_counter() - t0, 2),
                "source_deleted": source_deleted,
                "target_remote_path": target_remote_path,
            }
        except Exception as e:
            shadow_run.status = "failed"
            shadow_run.finished_at = datetime.utcnow()
            shadow_run.error_message = f"{type(e).__name__}: {str(e)[:500]}"
            try:
                await self.db.commit()
            except Exception:
                pass
            raise
        finally:
            try:
                if temp_file.exists():
                    temp_file.unlink()
            except Exception as cleanup_exc:
                logger.warning("Failed to cleanup temp %s: %s", temp_file, cleanup_exc)
