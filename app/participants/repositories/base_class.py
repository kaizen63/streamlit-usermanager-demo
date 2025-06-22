"""
Repository Base Module

This module defines the base class for all repository implementations.
It provides common functionality for database operations, transaction management,
and schema handling. The base class implements the context manager interface
for easy transaction management in with-statements.

For databases supporting a schema, the env variable DB_SCHEMA must be set to a non-empty string.
For SQLite or databases without schema support, it must be set to an empty string.
"""

import logging
import os
from typing import Self

from sqlmodel import Session

LOGGER_NAME: str = "participants"
logger = logging.getLogger(LOGGER_NAME)


class RepositoryBase:
    """
    Base class for all repository implementations.

    Provides common database operations and transaction management functionality.
    Implements the context manager interface for use in with-statements, which
    automatically handles rollback in case of exceptions.

    Attributes:
        session (Session): SQLModel database session for performing database operations

    """

    def __init__(self, session: Session) -> None:
        """
        Initialize the repository with a database session.

        Args:
            session: SQLModel session to use for database operations

        """
        self.session: Session = session

    def commit(self) -> None:
        """
        Commit the current transaction to the database.

        Attempts to commit changes to the database. If an exception occurs,
        logs a warning message but does not re-raise the exception.
        """
        try:
            self.session.commit()
        except Exception as e:
            logger.warning(f"Error when committing: {e}")

    def rollback(self) -> None:
        """
        Roll back the current transaction.

        Attempts to roll back any uncommitted changes. If an exception occurs,
        logs a warning message but does not re-raise the exception.
        """
        try:
            self.session.rollback()
        except Exception as e:
            logger.warning(f"Error when rolling back: {e}")

    @staticmethod
    def get_schema_prefix() -> str:
        """
        Get the database schema prefix based on environment configuration.

        Reads the environment variable DB_SCHEMA and returns the schema name
        with a trailing dot (for use in fully qualified table names) or an empty
        string if no schema is configured.

        Returns:
            str: Schema prefix (including trailing dot) or empty string if no schema

        """
        schema = os.getenv("DB_SCHEMA")
        if schema:
            return schema + "."
        return ""

    def __del__(self) -> None:
        """
        Destructor method called when instance is being destroyed.

        This method is intentionally left empty as a placeholder for cleanup
        operations if needed in the future.
        """

    def __enter__(self) -> Self:
        """
        Enter the context manager.

        This method is called when entering a with-block. Returns self to allow
        methods to be called on the context manager instance.

        Returns:
            Self: The repository instance itself

        """
        return self

    def __exit__(self, *exc_info: object) -> None:
        """
        Exit the context manager.

        This method is called when exiting a with-block. If an exception was raised
        within the with-block, rolls back the transaction automatically.

        Args:
            *exc_info: Exception information tuple (type, value, traceback)

        """
        # In case of an exception we roll back, otherwise do nothing
        if any(exc_info):
            self.session.rollback()
