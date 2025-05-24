import pathlib

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project Directories
ROOT = pathlib.Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Settings of the App, read either from environment or .env file"""

    DB_ENGINE: str = "sqlite"
    DB_USERNAME: str | None = ""
    DB_PASSWORD: str | None = None
    DB_SERVER: str | None = ""
    DB_PORT: int | None = None
    DB_DATABASE: str | None = "demo.sqlite"
    DB_DRIVER: str | None = ""
    DB_SCHEMA: str | None = ""

    model_config = SettingsConfigDict(
        case_sensitive=True, env_file=".env", env_file_encoding="utf-8"
    )


settings = Settings()
