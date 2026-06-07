import asyncio
from datetime import datetime, timedelta
import db, config
from alerts.telegram import send_telegram
from alerts.email_notify import send_email
from alerts.whatsapp import send_whatsapp

def _format_server_line(vps_id: str, hostname: str, cliente: str) -> str:
    return f"<b>{vps_id}</b> ({hostname} — {cliente})"

async def check_and_alert():
    stale_threshold = datetime.utcnow() - timedelta(hours=config.STALE_HOURS)
    with db.get_db() as conn:
        servers = conn.execute("SELECT vps_id, hostname, cliente FROM servers").fetchall()
        alerts = []
        for s in servers:
            vps_id, hostname, cliente = s["vps_id"], s["hostname"], s["cliente"]
            last_run = conn.execute(
                "SELECT status, reported_at FROM backup_runs WHERE vps_id=? ORDER BY id DESC LIMIT 1",
                (vps_id,)
            ).fetchone()
            if not last_run:
                alerts.append(("STALE", vps_id, hostname, cliente, "Nessun backup registrato"))
                continue
            if last_run["status"] == "failed":
                alerts.append(("FAILED", vps_id, hostname, cliente, "Backup fallito"))
                continue
            reported_at = datetime.fromisoformat(last_run["reported_at"])
            if reported_at < stale_threshold:
                alerts.append(("STALE", vps_id, hostname, cliente, f"Ultimo backup: {reported_at.strftime('%Y-%m-%d %H:%M')}"))
                continue
            # Check restore test
            last_restore = conn.execute(
                "SELECT status, checksum_ok FROM restore_runs WHERE vps_id=? ORDER BY id DESC LIMIT 1",
                (vps_id,)
            ).fetchone()
            if last_restore and (last_restore["status"] == "failed" or not last_restore["checksum_ok"]):
                alerts.append(("RESTORE_FAIL", vps_id, hostname, cliente, "Restore test fallito"))

    if not alerts:
        return

    # Build and send messages
    lines = []
    for kind, vps_id, hostname, cliente, detail in alerts:
        emoji = "🔴" if kind == "FAILED" else ("⚠️" if kind == "STALE" else "❌")
        lines.append(f"{emoji} {kind}: {_format_server_line(vps_id, hostname, cliente)} — {detail}")

    message = "\n".join(lines)
    full_alert = f"<b>Backup Monitor Alert</b>\n{message}"

    await send_telegram(full_alert)
    send_email(f"[BackupMonitor] {len(alerts)} alert", message.replace("<b>", "").replace("</b>", ""))
    if len(alerts) >= 3:
        await send_whatsapp(f"BACKUP ALERT: {len(alerts)} server con problemi!")
