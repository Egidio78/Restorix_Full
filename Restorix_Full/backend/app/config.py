from typing import Literal
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    app_name: str = "Restorix"
    app_env: Literal["development", "staging", "production"] = "production"

    # Database
    database_url: str

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Security
    secret_key: SecretStr
    encryption_key: SecretStr
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # CORS
    cors_origins: str = "http://localhost"

    # SMTP
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_from: str = "noreply@dbshield.io"

    # Retention
    RETENTION_ENABLED: bool = False

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
