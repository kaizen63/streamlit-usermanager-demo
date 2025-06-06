import logging
import os
import urllib
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.engine import Engine
from sqlalchemy.exc import PendingRollbackError
from sqlmodel import Session, SQLModel, create_engine

logger = logging.getLogger(__name__)


# def get_db_password(keyvault: str, secret: str) -> str:
#    """Read the db password from the keyvault"""
#    return get_secret(keyvault, secret) or ""


def is_sqlite(engine: Engine) -> bool:
    """Returns True if the engine is sqlite"""
    inspector = inspect(engine)
    return "sqlite" in inspector.dialect.name.lower()


def is_sqlserver(engine: Engine) -> bool:
    """Returns True if the engine is a sqlserver"""
    inspector = inspect(engine)
    return "mssql" in inspector.dialect.name.lower()


def get_url(db_engine: str | None = None) -> str:
    """Returns the database URL, defaulting to the DB_ENGINE environment variable if not provided."""
    db_engine = db_engine or os.getenv("DB_ENGINE")

    if not db_engine:
        raise ValueError(
            "Database engine must be specified either as an argument or via the DB_ENGINE environment variable"
        )

    db_server = urllib.parse.quote_plus(os.getenv("DB_SERVER", ""))
    db_port = int(os.getenv("DB_PORT", "0")) or None
    db_username = urllib.parse.quote_plus(os.getenv("DB_USERNAME", ""))
    db_password = urllib.parse.quote_plus(os.getenv("DB_PASSWORD", ""))
    db_database = (
        os.getenv("DB_DATABASE", "")
        if db_engine == "sqlite"
        else urllib.parse.quote_plus(os.getenv("DB_DATABASE", ""))
    )
    db_driver = urllib.parse.quote_plus(os.getenv("DB_DRIVER", ""))

    match db_engine:
        case "mssql":
            return f"mssql+pyodbc://{db_username}:{db_password}@{db_server}:{db_port}/{db_database}?driver={db_driver}"
        case "postgres":
            return f"postgresql+psycopg2://{db_username}:{db_password}@{db_server}:{db_port}/{db_database}"
        case "sqlite":
            return f"sqlite:///{db_database}"
        case _:
            raise ValueError(f"Unsupported database engine: {db_engine!a}")


def create_db_engine(
    db_url: str, db_schema: str | None = None, echo: bool = False
) -> Any:  # noqa: ANN401
    """
    Creates a database engine for the given URL.

    Use this if you do not want to use st.connection.
    Use case: Initialize the database before startup.
    """
    connect_args: dict[str, str | int | bool] = {}
    use_setinputsizes = None

    if db_url.startswith("postgres"):
        connect_args = {
            "sslmode": "require",
            "options": f"-csearch_path={db_schema}",
        }
    elif db_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    elif db_url.startswith("mssql"):
        connect_args = {
            "TrustServerCertificate": "yes",
            "Encrypt": "yes",
            "autocommit": False,
        }
        use_setinputsizes = False

    engine_params: dict[str, Any] = {
        "connect_args": connect_args,
        "echo": echo,
    }
    if use_setinputsizes is not None:
        engine_params["use_setinputsizes"] = use_setinputsizes

    return create_engine(db_url, **engine_params)


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


engine: Engine | None = None


def get_engine() -> Engine:
    """Returns the SQLAlchemy engine object from the SQLConnection"""
    global engine  # noqa: PLW0603
    if engine is not None:
        return engine
    engine = create_db_engine(get_url())
    return engine


@contextmanager
def get_session() -> Generator[Session]:
    """Get a session from the engine."""
    session = Session(bind=get_engine())
    try:
        session.connection()
        yield session  # Properly manages session
    except PendingRollbackError:
        session.rollback()
    finally:
        session.close()  # Ensures session cleanup
