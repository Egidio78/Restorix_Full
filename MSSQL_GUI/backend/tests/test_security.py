import pytest
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.encryption import encrypt, decrypt


def test_hash_password_returns_bcrypt_hash():
    hashed = hash_password("mypassword")
    assert hashed.startswith("$2b$")
    assert hashed != "mypassword"


def test_verify_password_correct():
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("mypassword")
    assert verify_password("wrongpassword", hashed) is False


def test_create_and_decode_access_token():
    token = create_access_token(subject="user-id-123", role="admin")
    payload = decode_token(token)
    assert payload["sub"] == "user-id-123"
    assert payload["role"] == "admin"
    assert payload["type"] == "access"


def test_create_and_decode_refresh_token():
    token = create_refresh_token(subject="user-id-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-id-123"
    assert payload["type"] == "refresh"


def test_decode_invalid_token_returns_none():
    result = decode_token("invalid.token.here")
    assert result is None


def test_encrypt_decrypt_roundtrip():
    plaintext = "sensitive_data_here"
    encrypted = encrypt(plaintext)
    assert encrypted != plaintext
    assert decrypt(encrypted) == plaintext


def test_encrypt_same_value_different_ciphertext():
    encrypted1 = encrypt("same_value")
    encrypted2 = encrypt("same_value")
    # AES-GCM usa nonce random, deve produrre ciphertext diversi
    assert encrypted1 != encrypted2
