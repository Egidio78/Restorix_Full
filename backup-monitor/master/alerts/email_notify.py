import smtplib
from email.mime.text import MIMEText
import config

def send_email(subject: str, body: str) -> bool:
    if not config.SMTP_HOST or not config.ALERT_EMAIL_TO:
        return False
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = config.SMTP_USER or "backup-monitor@localhost"
    msg["To"] = config.ALERT_EMAIL_TO
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as s:
            if config.SMTP_USER and config.SMTP_PASSWORD:
                s.starttls()
                s.login(config.SMTP_USER, config.SMTP_PASSWORD)
            s.send_message(msg)
        return True
    except Exception:
        return False
