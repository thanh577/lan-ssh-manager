from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    APP_NAME: str = "LAN SSH Manager"
    APP_SECRET_KEY: str = "change-me-secret-key-min-32-chars!!"
    APP_ENCRYPTION_KEY: str = ""  # Fernet key, auto-generated if empty (dev only)
    DATABASE_URL: str = "sqlite:///./data/lan_ssh_manager.db"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 480
    SSH_TIMEOUT: int = 10
    SSH_COMMAND_TIMEOUT: int = 30
    MAX_CONCURRENT_SSH: int = 10
    FILE_UPLOAD_MAX_MB: int = 50  # single-request upload (giữ trong RAM)
    FILE_UPLOAD_MAX_TOTAL_MB: int = 10240  # chunked upload (stream, không tốn RAM)
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
