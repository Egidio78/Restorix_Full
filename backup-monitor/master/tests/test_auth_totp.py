import pyotp
import auth.totp as totp

def test_encrypt_decrypt_roundtrip():
    secret = totp.generate_totp_secret()
    encrypted = totp.encrypt_secret(secret)
    assert totp.decrypt_secret(encrypted) == secret

def test_verify_totp_valid_code():
    secret = totp.generate_totp_secret()
    encrypted = totp.encrypt_secret(secret)
    code = pyotp.TOTP(secret).now()
    assert totp.verify_totp(encrypted, code) is True

def test_verify_totp_invalid_code():
    secret = totp.generate_totp_secret()
    encrypted = totp.encrypt_secret(secret)
    assert totp.verify_totp(encrypted, "000000") is False

def test_generate_qr_b64(monkeypatch):
    secret = totp.generate_totp_secret()
    b64 = totp.generate_qr_b64("admin", secret)
    import base64
    # should be valid base64
    decoded = base64.b64decode(b64)
    assert decoded[:4] == b'\x89PNG'

def test_generate_recovery_codes():
    codes = totp.generate_recovery_codes()
    assert len(codes) == 10
    assert all(len(c) == 16 for c in codes)
