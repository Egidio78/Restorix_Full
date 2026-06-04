"""Cross-platform remote path normalization for storage uploaders/streamers.

Agents on Windows may report file paths with backslashes (`C:\\Backup\\foo.bak`)
or mixed separators. Storage backends (S3, SFTP, FTP, WebDAV) all expect
forward slashes. This helper canonicalizes the path before storage operations.
"""
from __future__ import annotations
import re


def normalize_remote_path(path: str) -> str:
    """Convert backslash to forward slash, strip drive letter, collapse, validate.

    Examples:
        "C:\\Backup\\db.bak"  -> "Backup/db.bak"
        "backups\\2026\\foo"  -> "backups/2026/foo"
        "/backups/2026/foo"   -> "backups/2026/foo"
        "foo//bar"            -> "foo/bar"
        "../etc/passwd"       -> raises ValueError

    Raises:
        ValueError: if path contains traversal (..) or NULL bytes.
    """
    if not path:
        return path
    if "\x00" in path:
        raise ValueError("Path contains NULL byte")
    p = path.replace("\\", "/")
    p = re.sub(r"^[A-Za-z]:/?", "", p)
    p = re.sub(r"/+", "/", p)
    p = p.lstrip("/")
    if any(part == ".." for part in p.split("/")):
        raise ValueError(f"Path traversal not allowed: {path!r}")
    return p


def normalize_basename(path: str) -> str:
    """Extract just the filename portion, cross-platform.

    "C:\\Backup\\db.bak.enc" -> "db.bak.enc"
    "/var/backups/db.bak"    -> "db.bak"
    "db.bak"                 -> "db.bak"
    """
    if not path:
        return path
    p = path.replace("\\", "/")
    return p.rsplit("/", 1)[-1]
