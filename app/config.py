import pathlib

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root Directory (above app)
# This is where we log for the .env file
ROOT = pathlib.Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Settings of the App, read either from environment or .env file"""

    DB_USERNAME: str | None = None
    DB_PASSWORD: str | None = None
    DB_SERVER: str | None = None
    DB_PORT: int | None = None
    DB_DATABASE: str | None = None
    DB_DRIVER: str | None = None

    DB_SCHEMA: str | None = None

    LDAP_SERVER: str | None = None
    LOGGING_CONFIG: str | None = "log-config/logging-conf.yaml"
    LOGGING_LOG_LEVEL: str | None = "INFO"
    LOGGER_SERVICE: str | None = "stusermanagerdemo"

    POLICY_TTL: int | None = 60

    LOGGER_NAME: str | None = "stusermanagerdemo"

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=f"{ROOT!s}/.env",
        env_file_encoding="utf-8",
        extra="allow",
    )


settings = Settings()
