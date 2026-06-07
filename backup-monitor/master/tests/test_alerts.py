import asyncio
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import db

@pytest.mark.asyncio
async def test_check_and_alert_no_servers(fresh_db):
    from alerts.engine import check_and_alert
    # No servers → no alerts, no error
    await check_and_alert()

@pytest.mark.asyncio
async def test_check_and_alert_failed_backup(fresh_db):
    from alerts.engine import check_and_alert
    import hashlib, config
    api_key = hashlib.sha256(f"{config.MASTER_SECRET}vps-001".encode()).hexdigest()
    with db.get_db() as conn:
        conn.execute("INSERT INTO servers (vps_id, hostname, cliente, api_key) VALUES (?,?,?,?)",
                     ("vps-001", "h1", "Acme", api_key))
        conn.execute("INSERT INTO backup_runs (vps_id, status) VALUES (?,?)", ("vps-001", "failed"))

    sent = []
    with patch("alerts.engine.send_telegram", new_callable=AsyncMock, return_value=True) as mock_tg, \
         patch("alerts.engine.send_email", return_value=True) as mock_email:
        await check_and_alert()
        assert mock_tg.called
        assert mock_email.called
        call_args = mock_tg.call_args[0][0]
        assert "vps-001" in call_args

@pytest.mark.asyncio
async def test_check_and_alert_ok_no_alert(fresh_db):
    from alerts.engine import check_and_alert
    from datetime import datetime, timedelta
    import hashlib, config
    api_key = hashlib.sha256(f"{config.MASTER_SECRET}vps-001".encode()).hexdigest()
    recent = datetime.utcnow().isoformat()
    with db.get_db() as conn:
        conn.execute("INSERT INTO servers (vps_id, hostname, cliente, api_key) VALUES (?,?,?,?)",
                     ("vps-001", "h1", "Acme", api_key))
        conn.execute("INSERT INTO backup_runs (vps_id, status, reported_at) VALUES (?,?,?)",
                     ("vps-001", "ok", recent))
    with patch("alerts.engine.send_telegram", new_callable=AsyncMock) as mock_tg:
        await check_and_alert()
        assert not mock_tg.called

def test_send_telegram_no_config():
    import asyncio
    import config
    config.TELEGRAM_BOT_TOKEN = ""
    from alerts.telegram import send_telegram
    result = asyncio.run(send_telegram("test"))
    assert result is False

def test_send_whatsapp_no_config():
    import asyncio
    import config
    config.CALLMEBOT_PHONE = ""
    from alerts.whatsapp import send_whatsapp
    result = asyncio.run(send_whatsapp("test"))
    assert result is False

def test_send_email_no_config():
    import config
    config.SMTP_HOST = ""
    from alerts.email_notify import send_email
    result = send_email("subject", "body")
    assert result is False
