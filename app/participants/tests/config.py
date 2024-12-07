import pathlib
import platform
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project Directories
ROOT = pathlib.Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Settings of the App, read either from environment or .env file"""

    DB_USERNAME: Optional[str] = "ccoeservice"
    DB_PASSWORD: Optional[str] = None
    DB_SERVER: Optional[str] = "cloudcost.database.windows.net"
    DB_PORT: Optional[int] = 1433
    DB_DATABASE: Optional[str] = "CLOUD_COST_MGMT"
    DB_DRIVER: str = (
        "SQL Server"
        if platform.system() == "Windows"
        else "ODBC Driver 18 for SQL Server"
    )
    DB_SCHEMA: Optional[str] = "cloudcost_devx"

    model_config = SettingsConfigDict(
        case_sensitive=True, env_file=".env", env_file_encoding="utf-8"
    )


settings = Settings()
