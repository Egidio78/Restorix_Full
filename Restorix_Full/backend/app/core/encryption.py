import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import get_settings


def _get_key() -> bytes:
    key_hex = get_settings().encryption_key.get_secret_value()
    if len(key_hex) != 64:
        raise ValueError(
            f"ENCRYPTION_KEY must be exactly 64 hex characters (32 bytes); got {len(key_hex)}"
        )
    return bytes.fromhex(key_hex)


def encrypt(plaintext: str) -> str:
    """Cifra una stringa con AES-256-GCM. Ritorna base64(nonce + ciphertext)."""
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    combined = nonce + ciphertext
    return base64.b64encode(combined).decode()


def decrypt(encrypted: str) -> str:
    """Decifra una stringa cifrata con encrypt()."""
    key = _get_key()
    aesgcm = AESGCM(key)
    combined = base64.b64decode(encrypted.encode())
    nonce = combined[:12]
    ciphertext = combined[12:]
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode()
