from __future__ import annotations
"""Filesystem folder backup using tar+gzip."""
import logging
import os
import subprocess
from datetime import datetime

logger = logging.getLogger(__name__)


def create_folder_backup(folder_path: str, output_dir: str, job_name: str = "folder") -> str:
    """
    Create a tar.gz archive of the given folder.
    Returns path to the .tar.gz file.

    Permission handling:
      - Uses `--ignore-failed-read` so unreadable files (e.g. other users' home
        subdirs when the agent isn't root) don't abort the backup.
      - tar exit code 1 means "some files differed/were skipped" — we treat it
        as success and log the warnings. Exit code >= 2 is a real failure.
    """
    if not os.path.isdir(folder_path):
        raise RuntimeError(f"Folder does not exist or is not a directory: {folder_path}")

    if not os.access(folder_path, os.R_OK):
        raise RuntimeError(
            f"Folder is not readable by the agent user: {folder_path}. "
            "Run the agent as root, or grant read access to the 'dbshield' user."
        )

    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in job_name)
    archive_name = f"{safe_name}_{timestamp}.tar.gz"
    archive_path = os.path.join(output_dir, archive_name)

    # --ignore-failed-read: don't abort on files we can't read (e.g. other users' SSH keys)
    # --warning=no-file-changed: silence noisy warnings about active log files etc.
    cmd = [
        "tar",
        "--ignore-failed-read",
        "--warning=no-file-changed",
        "--warning=no-file-removed",
        "-czf",
        archive_path,
        "-C",
        "/",
        folder_path.lstrip("/"),
    ]

    logger.info(f"Creating folder backup: {folder_path} -> {archive_path}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    except FileNotFoundError:
        raise RuntimeError("tar command not found")

    # Exit code semantics (GNU tar):
    #   0 = success
    #   1 = some files differed or were skipped (e.g. permission denied with --ignore-failed-read)
    #   2 = fatal error
    if result.returncode >= 2:
        stderr_tail = (result.stderr or result.stdout or "").strip().splitlines()[-5:]
        raise RuntimeError(
            f"tar failed (exit {result.returncode}): {' | '.join(stderr_tail)}"
        )

    if result.returncode == 1 and result.stderr:
        # Log skipped-file warnings so user knows what was missed
        skipped_lines = [ln for ln in result.stderr.splitlines() if "Cannot" in ln or "permission" in ln.lower()][:10]
        if skipped_lines:
            logger.warning(
                "tar completed with %d skipped file(s) (e.g. permission denied). First few: %s",
                len(skipped_lines),
                " | ".join(skipped_lines),
            )

    if not os.path.exists(archive_path):
        raise RuntimeError(f"Archive not created: {archive_path}")

    size_bytes = os.path.getsize(archive_path)
    logger.info(f"Folder backup created: {archive_path} ({size_bytes} bytes)")
    return archive_path
