"""Helpers for MSSQL database discovery via agent."""
import json
import uuid
import redis.asyncio as aioredis
from app.config import get_settings
from app.core.encryption import encrypt, decrypt

REQUEST_KEY_PREFIX = "dbshield:discover:req:"
RESULT_KEY_PREFIX = "dbshield:discover:res:"
TTL_SECONDS = 120


async def _redis_client():
    settings = get_settings()
    return await aioredis.from_url(settings.redis_url, decode_responses=True)


async def store_request(server_id: uuid.UUID, connection_string: str, username: str, password: str, engine: str = "mssql") -> None:
    r = await _redis_client()
    try:
        payload = encrypt(json.dumps({
            "connection_string": connection_string,
            "username": username,
            "password": password,
            "engine": engine,
        }))
        await r.setex(f"{REQUEST_KEY_PREFIX}{server_id}", TTL_SECONDS, payload)
        await r.delete(f"{RESULT_KEY_PREFIX}{server_id}")
    finally:
        await r.aclose()


async def get_request_for_agent(server_id: uuid.UUID) -> dict | None:
    r = await _redis_client()
    try:
        payload = await r.get(f"{REQUEST_KEY_PREFIX}{server_id}")
    finally:
        await r.aclose()
    if not payload:
        return None
    try:
        return json.loads(decrypt(payload))
    except Exception:
        return None


async def consume_request(server_id: uuid.UUID) -> None:
    r = await _redis_client()
    try:
        await r.delete(f"{REQUEST_KEY_PREFIX}{server_id}")
    finally:
        await r.aclose()


async def store_result(server_id: uuid.UUID, databases: list[str], error: str | None) -> None:
    r = await _redis_client()
    try:
        payload = json.dumps({"databases": databases, "error": error})
        await r.setex(f"{RESULT_KEY_PREFIX}{server_id}", TTL_SECONDS, payload)
    finally:
        await r.aclose()


async def get_result(server_id: uuid.UUID) -> dict | None:
    r = await _redis_client()
    try:
        payload = await r.get(f"{RESULT_KEY_PREFIX}{server_id}")
    finally:
        await r.aclose()
    if not payload:
        return None
    try:
        return json.loads(payload)
    except Exception:
        return None
