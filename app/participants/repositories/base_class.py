"""Base class for all repositories
Implements the context manager interface.
For databases supporting a schema, the env variable DB_SCHEMA must be set to a non-empty string
For SQLite or others it must be set to an empty string
"""

import os
import logging
from typing import Any, Self

from sqlmodel import Session

logger = logging.getLogger("participants")


class RepositoryBase:
    """Basic functionality for all base classes"""

    def __init__(self, session: Session) -> None:
        self.session: Session = session

    def commit(self) -> None:
        """Commits if the database is connected"""
        try:
            self.session.commit()
        except Exception:
            logger.warning("Error when committing: {e}")

    def rollback(self) -> None:
        """Rolls back if the database is connected"""
        try:
            self.session.rollback()
        except Exception:
            logger.warning("Error when rolling back: {e}")

    @staticmethod
    def get_schema_prefix() -> str:
        """Reads the environment variable DB_SCHEMA and returns the schema prefix (including the dot) or an empty string"""
        schema = os.getenv("DB_SCHEMA")
        if schema:
            return schema + "."
        return ""

    def __del__(self) -> None:
        pass

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: tuple[Any, ...]) -> None:
        # In case of an exception we roll back, otherwise do nothing
        if any(exc_info):
            self.session.rollback()
