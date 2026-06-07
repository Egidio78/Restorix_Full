import os

MASTER_SECRET = os.environ["MASTER_SECRET"]
JWT_SECRET = os.environ["JWT_SECRET"]
TOTP_ENCRYPTION_KEY = os.environ["TOTP_ENCRYPTION_KEY"]
DB_PATH = os.environ.get("DB_PATH", "backup_monitor.db")
MASTER_BASE_URL = os.environ.get("MASTER_BASE_URL", "http://localhost:8080")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
ALERT_EMAIL_TO = os.environ.get("ALERT_EMAIL_TO", "")

CALLMEBOT_PHONE = os.environ.get("CALLMEBOT_PHONE", "")
CALLMEBOT_APIKEY = os.environ.get("CALLMEBOT_APIKEY", "")

STALE_HOURS = int(os.environ.get("STALE_HOURS", "25"))
LARGE_FILE_THRESHOLD_GB = float(os.environ.get("LARGE_FILE_THRESHOLD_GB", "5.0"))
