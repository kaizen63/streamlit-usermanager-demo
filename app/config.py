import pathlib
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root Directory (above app)
# This is where we log for the .env file
ROOT = pathlib.Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Settings of the App, read either from environment or .env file"""

    DB_USERNAME: Optional[str] = None
    DB_PASSWORD: Optional[str] = None
    DB_SERVER: Optional[str] = None
    DB_PORT: Optional[int] = None
    DB_DATABASE: Optional[str] = None
    DB_DRIVER: Optional[str] = None

    DB_SCHEMA: Optional[str] = None

    LDAP_SERVER: Optional[str] = None
    LOGGING_CONFIG: Optional[str] = "log-config/logging-conf.yaml"
    LOGGING_LOG_LEVEL: Optional[str] = "INFO"
    LOGGER_SERVICE: Optional[str] = "stusermanagerdemo"

    POLICY_TTL: Optional[int] = 60

    LOGGER_NAME: Optional[str] = "stusermanagerdemo"

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=f"{str(ROOT)}/.env",
        env_file_encoding="utf-8",
        extra="allow",
    )


settings = Settings()
