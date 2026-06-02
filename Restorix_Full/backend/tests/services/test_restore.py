import os
from unittest.mock import MagicMock, patch

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException

from app.services.restore import RestoreService
from app.services.restore_crypto import (
    MAGIC,
    NONCE_LEN,
    SALT_LEN,
    decrypt_file_aesgcm,
    derive_key,
)


def test_preflight_disk_raises_507_when_insufficient(tmp_path):
    service = RestoreService(db=MagicMock())
    with patch("app.services.restore.shutil.disk_usage") as du:
        du.return_value = MagicMock(free=1024)
        with pytest.raises(HTTPException) as exc:
            service._preflight_disk_space(tmp_path, required_bytes=10 * 1024 ** 3)
        assert exc.value.status_code == 507


def test_preflight_disk_passes_with_enough_space(tmp_path):
    service = RestoreService(db=MagicMock())
    with patch("app.services.restore.shutil.disk_usage") as du:
        du.return_value = MagicMock(free=100 * 1024 ** 3)
        service._preflight_disk_space(tmp_path, required_bytes=10 * 1024 ** 3)


def test_validate_temp_dir_rejects_traversal():
    service = RestoreService(db=MagicMock())
    with pytest.raises(HTTPException) as exc:
        service._validate_temp_dir("../../etc/passwd")
    assert exc.value.status_code in (400, 422)


def test_validate_temp_dir_rejects_relative():
    service = RestoreService(db=MagicMock())
    with pytest.raises(HTTPException) as exc:
        service._validate_temp_dir("relative/path")
    assert exc.value.status_code == 400


def test_derived_filename_strips_enc_suffix_when_decrypted():
    assert RestoreService._derived_filename("path/to/db.bak.enc", decrypted=True) == "db.bak"
    assert RestoreService._derived_filename("path/to/db.bak.enc", decrypted=False) == "db.bak.enc"


def test_derived_filename_unchanged_without_enc():
    assert RestoreService._derived_filename("path/to/db.bak.gz", decrypted=False) == "db.bak.gz"


def test_decrypt_roundtrip_matches_agent_format(tmp_path):
    plaintext = b"hello world" * 1000
    password = "secretpw"

    salt = os.urandom(SALT_LEN)
    nonce = os.urandom(NONCE_LEN)
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    enc_file = tmp_path / "test.enc"
    with open(enc_file, "wb") as f:
        f.write(MAGIC + salt + nonce + ciphertext)

    dec_file = tmp_path / "test.dec"
    decrypt_file_aesgcm(enc_file, dec_file, password)

    assert dec_file.read_bytes() == plaintext
