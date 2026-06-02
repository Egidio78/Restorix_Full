"""RestoreService: presigned S3 redirect OR streaming proxy with optional AES-GCM decrypt."""
import json
import logging
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator

from fastapi import BackgroundTasks, HTTPException
from fastapi.responses import RedirectResponse, StreamingResponse


@dataclass
class SendToTempResult:
    target_path: str
    folder_path: str
    bytes: int
    decrypted: bool
    duration_seconds: float

logger = logging.getLogger(__name__)

CHUNK_SIZE = 4 * 1024 * 1024  # 4 MiB
DISK_SAFETY_MARGIN = 1.2       # need free space >= file_size * 1.2
DEFAULT_TEMP_DIR = "/var/lib/dbshield/restore-tmp"


class RestoreService:
    def __init__(self, db):
        self.db = db

    def _validate_temp_dir(self, raw: str) -> Path:
        if not raw or ".." in raw or not raw.startswith("/"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid restore_temp_dir: {raw!r}",
            )
        return Path(raw).resolve()

    def _preflight_disk_space(self, temp_dir: Path, required_bytes: int) -> None:
        usage = shutil.disk_usage(str(temp_dir))
        needed = int(required_bytes * DISK_SAFETY_MARGIN)
        if usage.free < needed:
            free_gb = usage.free / (1024 ** 3)
            needed_gb = needed / (1024 ** 3)
            raise HTTPException(
                status_code=507,
                detail=(
                    f"Spazio insufficiente nella cartella temp `{temp_dir}`: "
                    f"servono {needed_gb:.2f} GB, disponibili {free_gb:.2f} GB. "
                    "Cambia la cartella in Impostazioni -> Organizzazione, o libera spazio."
                ),
            )

    @staticmethod
    def _derived_filename(remote_filename: str, decrypted: bool) -> str:
        base = Path(remote_filename).name
        if decrypted and base.endswith(".enc"):
            base = base[:-4]
        return base

    @staticmethod
    def _cleanup(path: Path) -> None:
        try:
            if path.exists():
                path.unlink()
        except Exception as e:  # noqa: BLE001
            logger.warning("Cleanup failed for %s: %s", path, e)

    async def _iter_file(self, path: Path) -> AsyncIterator[bytes]:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk:
                    break
                yield chunk

    async def generate_response(
        self,
        run,
        decrypt: bool,
        background_tasks: BackgroundTasks,
    ):
        """Return RedirectResponse (S3 presigned) or StreamingResponse (proxy)."""
        from app.core.encryption import decrypt as decrypt_str
        from app.services.streamers import get_streamer

        sd = run.job.storage_destination
        config = json.loads(decrypt_str(sd.config_enc))
        storage_type = sd.storage_type
        storage_type_str = storage_type.value if hasattr(storage_type, "value") else storage_type
        streamer = get_streamer(storage_type_str, config)

        remote_path = run.file_path
        if not remote_path:
            raise HTTPException(status_code=410, detail="Run has no remote file path")

        # CASE A: S3 + no decrypt -> presigned URL
        if storage_type_str == "s3" and not decrypt:
            url = streamer.generate_presigned_url(remote_path, ttl_seconds=900)
            return RedirectResponse(url=url, status_code=302)

        # CASE B: streaming proxy
        from app.models.organization import Organization as _Org
        org = await self.db.get(_Org, run.job.org_id)
        temp_dir = self._validate_temp_dir(
            getattr(org, "restore_temp_dir", None) or DEFAULT_TEMP_DIR
        )
        temp_dir.mkdir(parents=True, exist_ok=True)

        remote_size = streamer.head_size(remote_path)
        required = remote_size * 2 if decrypt else remote_size
        self._preflight_disk_space(temp_dir, required)

        token = uuid.uuid4().hex
        suffix = ".enc" if decrypt else ""
        downloaded = temp_dir / f"restore-{token}{suffix}"
        streamer.download_to_file(remote_path, downloaded)

        if decrypt:
            from app.services.restore_crypto import decrypt_file_aesgcm
            decrypted_path = temp_dir / f"restore-{token}.dec"
            password_enc = run.job.encryption_password_enc
            if not password_enc:
                raise HTTPException(
                    status_code=500,
                    detail="Job has no encryption password but decrypt was requested",
                )
            password = decrypt_str(password_enc)
            try:
                decrypt_file_aesgcm(downloaded, decrypted_path, password)
            finally:
                self._cleanup(downloaded)
            file_to_serve = decrypted_path
            filename = self._derived_filename(remote_path, decrypted=True)
        else:
            file_to_serve = downloaded
            filename = self._derived_filename(remote_path, decrypted=False)

        background_tasks.add_task(self._cleanup, file_to_serve)

        return StreamingResponse(
            self._iter_file(file_to_serve),
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(file_to_serve.stat().st_size),
            },
        )

    @staticmethod
    def _safe_folder_name(file_path: str) -> str:
        """Build 'restore_<sanitized>' from file_path basename.

        Strips multi-extensions (.bak.gz.enc -> stem) and sanitizes
        to alphanumeric + underscore/dash.
        """
        stem = Path(file_path).name
        # strip multi-extensions like .bak.gz.enc
        while True:
            new = Path(stem).stem
            if new == stem:
                break
            stem = new
        cleaned = re.sub(r"[^A-Za-z0-9_\-]", "_", stem)
        cleaned = re.sub(r"_+", "_", cleaned).strip("_")
        return f"restore_{cleaned or 'backup'}"

    async def send_to_temp(
        self,
        run,
        decrypt: bool,
    ) -> SendToTempResult:
        """Download run from remote storage and write to platform temp dir under restore_<name>/."""
        from app.core.encryption import decrypt as decrypt_str
        from app.services.streamers import get_streamer
        from time import perf_counter

        sd = run.job.storage_destination
        config = json.loads(decrypt_str(sd.config_enc))
        storage_type = sd.storage_type
        storage_type_str = storage_type.value if hasattr(storage_type, "value") else storage_type

        from app.models.organization import Organization as _Org
        org = await self.db.get(_Org, run.job.org_id)
        base_temp = self._validate_temp_dir(
            getattr(org, "restore_temp_dir", None) or DEFAULT_TEMP_DIR
        )
        base_temp.mkdir(parents=True, exist_ok=True)

        remote_path = run.file_path
        if not remote_path:
            raise HTTPException(status_code=410, detail="Run has no remote file path")

        streamer = get_streamer(storage_type_str, config)
        remote_size = streamer.head_size(remote_path)

        # Pre-flight disk (heavier multiplier when decrypting: need both .enc and decrypted)
        required = int(remote_size * (2.2 if decrypt else 1.2))
        self._preflight_disk_space(base_temp, required)

        folder_name = self._safe_folder_name(remote_path)
        folder = base_temp / folder_name
        folder.mkdir(exist_ok=True)
        try:
            os.chmod(folder, 0o770)
        except Exception:
            pass

        downloaded_name = Path(remote_path).name
        encrypted_local = folder / downloaded_name

        t0 = perf_counter()
        streamer.download_to_file(remote_path, encrypted_local)

        final_path = encrypted_local
        if decrypt:
            from app.services.restore_crypto import decrypt_file_aesgcm
            final_name = (
                downloaded_name[:-4]
                if downloaded_name.endswith(".enc")
                else downloaded_name + ".dec"
            )
            final_path = folder / final_name
            try:
                if not run.job.encryption_password_enc:
                    raise HTTPException(
                        status_code=400,
                        detail="Job non ha encryption_password configurata ma decrypt richiesto",
                    )
                password = decrypt_str(run.job.encryption_password_enc)
                decrypt_file_aesgcm(encrypted_local, final_path, password)
            finally:
                if final_path != encrypted_local and final_path.exists():
                    self._cleanup(encrypted_local)
        t1 = perf_counter()

        size_final = final_path.stat().st_size if final_path.exists() else 0

        return SendToTempResult(
            target_path=str(final_path),
            folder_path=str(folder),
            bytes=size_final,
            decrypted=decrypt,
            duration_seconds=round(t1 - t0, 2),
        )
