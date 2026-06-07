import hashlib
from fastapi import HTTPException
import config

def verify_api_key(vps_id: str, api_key: str):
    expected = hashlib.sha256(f"{config.MASTER_SECRET}{vps_id}".encode()).hexdigest()
    if api_key != expected:
        raise HTTPException(status_code=401, detail="API key non valida")
