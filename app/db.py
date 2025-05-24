"""Connects us to the database via streamlits SQLConnection which is a wrapper around SQLAlchemy"""

import functools
import logging
import os
import urllib
from collections.abc import Generator
from typing import Any

import streamlit as st
from config import settings
from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import PendingRollbackError
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine
from streamlit.connections import SQLConnection
from who_called_me import who_called_me

logger = logging.getLogger(settings.LOGGER_NAME)


def get_url(db_engine: str | None = None) -> str:
    """Returns the db_url. If db_engine is None we read it from env variable DB_ENGINE"""
    if db_engine is None:
        db_engine = os.getenv("DB_ENGINE")

    db_server = urllib.parse.quote_plus(os.getenv("DB_SERVER", ""))
    db_port = int(port_s) if (port_s := os.getenv("DB_PORT")) else None

    db_username = urllib.parse.quote_plus(os.getenv("DB_USERNAME", ""))
    db_password = urllib.parse.quote_plus(os.getenv("DB_PASSWORD", ""))
    db_database = urllib.parse.quote_plus(os.getenv("DB_DATABASE", ""))
    db_driver = urllib.parse.quote_plus(os.getenv("DB_DRIVER", ""))
    # db_schema = os.getenv("DB_SCHEMA")

    if db_engine == "sqlite":
        db_database = os.getenv("DB_DATABASE", "")  # No quoting for sqlite

    if db_engine == "mssql":
        db_url = f"mssql+pyodbc://{db_username}:{db_password}@{db_server}:{db_port}/{db_database}?driver={db_driver}"
    elif db_engine == "postgres":  # Postgres:
        db_url = f"postgresql+psycopg2://{db_username}:{db_password}@{db_server}:{db_port}/{db_database}"
    elif db_engine == "sqlite":
        db_url = f"sqlite:///{db_database}"
    else:
        raise ValueError(f"db_engine {db_engine} not supported")

    return db_url


def create_connection(
    db_url: str, db_schema: str | None = None, echo: bool = False
) -> SQLConnection:
    """Creates a (cached) streamlit connection. With this call you have access to the engine and the session"""
    if db_schema is None:
        db_schema = os.getenv("DB_SCHEMA", None)

    # Needed for mssql only
    use_setinputsizes = None

    if db_url.startswith("mssql"):
        connect_args = {
            "check_same_thread": False,
            "TrustServerCertificate": "yes",
            "Encrypt": "yes",
            "autocommit": False,
            # "pool_pre_ping": True,
        }
        use_setinputsizes = False
    elif db_url.startswith("postgres"):
        connect_args = {
            "sslmode": "require",
            "options": f"-csearch_path={db_schema}",
        }
    elif db_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    else:
        connect_args = {}

    logger.debug(f"Connecting to database: {db_url}. Caller={who_called_me(1)}")
    if use_setinputsizes is None:
        connection = st.connection(
            "mydb",
            type="sql",
            url=db_url,
            connect_args=connect_args,
            ttl=300,
            echo=echo,
            poolclass=StaticPool,
        )
    else:
        # Note. The ttl is the default ttl for queries using connection.query
        connection = st.connection(
            "mydb",
            type="sql",
            url=db_url,
            connect_args=connect_args,
            ttl=300,
            use_setinputsizes=use_setinputsizes,
            echo=echo,
        )

    return connection


def get_db() -> Session:
    """Returns the session object from the SQLConnection"""
    session = Session(bind=get_engine())
    try:
        _ = session.connection()
    except PendingRollbackError:
        session.rollback()
    return session


def get_engine() -> Engine:
    """Returns the SQLAlchemy engine object from the SQLConnection"""
    if connection := st.session_state.get("db_connection"):
        return connection.engine

    connection = create_connection(get_url(), echo=True)
    st.session_state["db_connection"] = connection
    return connection.engine


def get_session_generator(engine: Engine) -> Generator[Session]:
    session = Session(bind=engine)
    try:
        _ = session.connection()
    except PendingRollbackError:
        session.rollback()
    yield session
    session.close()


def get_session(engine: Engine) -> Session:
    """
    Get the db session.

    To be used with:
    with get_session(engine) as session:
     ...
    """
    return next(get_session_generator(engine))


@functools.cache
def is_sqlserver(engine: Engine) -> bool:
    """Returns True if the engine is a sqlserver"""
    inspector = inspect(engine)
    return "mssql" in inspector.dialect.name.lower()


@functools.cache
def is_sqlite(engine: Engine) -> bool:
    """Returns True if the engine is sqlite"""
    inspector = inspect(engine)
    return "sqlite" in inspector.dialect.name.lower()


def inject_sa_column_kwargs(
    model: Any,  # noqa: ANN401
    column_name: str,
    sa_column_kwargs: dict[str, Any],
) -> None:
    # Get the table object from SQLAlchemy metadata
    table = model.__table__

    # Check if the column exists in the table
    if column_name in table.columns:
        # Access the existing column
        column = table.columns[column_name]

        # Dynamically modify the column using sa_column_kwargs
        for key, value in sa_column_kwargs.items():
            setattr(column, key, value)
    else:
        raise ValueError(f"Column {column_name} not found in {model.__name__} table.")


def create_db_and_tables(engine: Engine) -> None:
    """Creates the database and the tables"""
    try:
        with Session(engine) as db:
            #            print("")
            #            for table_name in SQLModel.metadata.tables.keys():
            #                print(f"Creating table: {table_name}")
            SQLModel.metadata.create_all(engine, checkfirst=True)
            db.commit()
            db.flush()
    except Exception as e:
        print(e)
        db.rollback()
        raise


def create_db_engine(
    db_url: str,
    db_schema: str | None = None,
    echo: bool = False,
    **kwargs: Any,  # noqa: ANN401
) -> Any:  # noqa: ANN401
    """
    Creates a db engine for the url.

    Use this if you do not want to use the st.connection.
    Use case: Initialize the db before startup
    """
    use_setinputsizes = None
    if db_url.startswith("postgres"):
        connect_args: dict[str, Any] = {
            "sslmode": "require",
            "options": f"-csearch_path={db_schema}",
        }
    elif db_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    elif db_url.startswith("mssql"):
        connect_args = {
            "check_same_thread": False,
            "TrustServerCertificate": "yes",
            "Encrypt": "yes",
            "autocommit": False,
        }
        use_setinputsizes = False

    else:
        connect_args = {}
    if use_setinputsizes is None:
        engine = create_engine(db_url, connect_args=connect_args, echo=echo, **kwargs)
    else:
        engine = create_engine(
            db_url,
            connect_args=connect_args,
            echo=echo,
            use_setinputsizes=use_setinputsizes,
            **kwargs,
        )

    return engine
