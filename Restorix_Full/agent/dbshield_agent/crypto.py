from __future__ import annotations
import gzip
import logging
import os
import shutil

logger = logging.getLogger(__name__)


def compress_file(input_path: str) -> str:
    output_path = input_path + ".gz"
    with open(input_path, "rb") as f_in, gzip.open(output_path, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    os.remove(input_path)
    logger.info(f"Compressed: {output_path}")
    return output_path


def encrypt_file(input_path: str, password: str) -> str:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

    output_path = input_path + ".enc"
    salt = os.urandom(16)
    kdf = Scrypt(salt=salt, length=32, n=2**14, r=8, p=1)
    key = kdf.derive(password.encode())

    aesgcm = AESGCM(key)
    nonce = os.urandom(12)

    with open(input_path, "rb") as f:
        plaintext = f.read()

    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    with open(output_path, "wb") as f:
        f.write(b"DSH1")
        f.write(salt)
        f.write(nonce)
        f.write(ciphertext)

    os.remove(input_path)
    logger.info(f"Encrypted: {output_path}")
    return output_path
