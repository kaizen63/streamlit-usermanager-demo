import pathlib
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project Directories
ROOT = pathlib.Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Settings of the App, read either from environment or .env file"""

    DB_ENGINE: str = "sqlite"
    DB_USERNAME: Optional[str] = ""
    DB_PASSWORD: Optional[str] = None
    DB_SERVER: Optional[str] = ""
    DB_PORT: Optional[int] = None
    DB_DATABASE: Optional[str] = "demo.sqlite"
    DB_DRIVER: Optional[str] = ""
    DB_SCHEMA: Optional[str] = ""

    model_config = SettingsConfigDict(
        case_sensitive=True, env_file=".env", env_file_encoding="utf-8"
    )


settings = Settings()
