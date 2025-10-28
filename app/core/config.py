from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import EmailStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Rocks Monitoramento Backend"
    debug: bool = True
    database_url: str = "sqlite+aiosqlite:///" + str(Path(__file__).resolve().parents[2] / "app.db")
    jwt_secret_key: str = "change_me"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60 * 24
    rate_limit_requests: int = 120
    rate_limit_window_seconds: int = 60
    log_level: str = "INFO"
    api_prefix: str = "/api"
    cors_allow_origins: list[str] = ["*"]
    initial_admin_email: Optional[EmailStr] = None
    initial_admin_password: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
