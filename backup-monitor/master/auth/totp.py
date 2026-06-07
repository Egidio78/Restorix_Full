import pyotp, qrcode, io, base64, secrets
from cryptography.fernet import Fernet
import config

def _fernet() -> Fernet:
    # TOTP_ENCRYPTION_KEY must be a url-safe base64-encoded 32-byte key
    # (e.g. generated with: base64.urlsafe_b64encode(os.urandom(32)))
    key = config.TOTP_ENCRYPTION_KEY.encode()
    # Ensure correct padding and derive exactly 32 bytes
    raw = base64.urlsafe_b64decode(key + b"==")
    padded = (raw + b"\x00" * 32)[:32]
    return Fernet(base64.urlsafe_b64encode(padded))

def generate_totp_secret() -> str:
    return pyotp.random_base32()

def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()

def decrypt_secret(encrypted: str) -> str:
    return _fernet().decrypt(encrypted.encode()).decode()

def verify_totp(encrypted_secret: str, code: str) -> bool:
    secret = decrypt_secret(encrypted_secret)
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)

def generate_qr_b64(username: str, secret: str) -> str:
    uri = pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name="BackupMonitor")
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

def generate_recovery_codes() -> list[str]:
    return [secrets.token_hex(8) for _ in range(10)]
