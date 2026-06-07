import httpx
import config

async def send_telegram(message: str) -> bool:
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.post(url, json={"chat_id": config.TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"})
            return r.status_code == 200
        except Exception:
            return False
