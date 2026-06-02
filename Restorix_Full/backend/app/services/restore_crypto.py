"""AES-256-GCM file decryption matching the agent's encrypt_file format.

The agent (agent/dbshield_agent/crypto.py) writes:
    [magic b'DSH1' (4)] [salt(16)] [nonce(12)] [ciphertext+tag(N)]

Scrypt params: n=2**14, r=8, p=1, key length 32 bytes (AES-256).
"""
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


MAGIC = b"DSH1"
MAGIC_LEN = 4
SALT_LEN = 16
NONCE_LEN = 12
SCRYPT_N = 2 ** 14
SCRYPT_R = 8
SCRYPT_P = 1
KEY_LEN = 32  # AES-256


def derive_key(password: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=KEY_LEN, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)
    return kdf.derive(password.encode("utf-8"))


def decrypt_file_aesgcm(src: Path, dst: Path, password: str) -> None:
    """Decrypt a file produced by the agent's encrypt_file."""
    with open(src, "rb") as f:
        magic = f.read(MAGIC_LEN)
        if magic != MAGIC:
            raise ValueError(
                f"Encrypted file magic mismatch: expected {MAGIC!r}, got {magic!r}"
            )
        salt = f.read(SALT_LEN)
        nonce = f.read(NONCE_LEN)
        ciphertext = f.read()

    if len(salt) != SALT_LEN or len(nonce) != NONCE_LEN:
        raise ValueError("Encrypted file is truncated or corrupt")

    key = derive_key(password, salt)
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)

    with open(dst, "wb") as f:
        f.write(plaintext)
