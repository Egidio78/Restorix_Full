import httpx
import config

async def send_whatsapp(message: str) -> bool:
    if not config.CALLMEBOT_PHONE or not config.CALLMEBOT_APIKEY:
        return False
    url = "https://api.callmebot.com/whatsapp.php"
    params = {"phone": config.CALLMEBOT_PHONE, "text": message, "apikey": config.CALLMEBOT_APIKEY}
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            r = await client.get(url, params=params)
            return r.status_code == 200
        except Exception:
            return False
