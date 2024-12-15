from typing import Any

from sqlmodel import create_engine, SQLModel, Session
import logging
import os
import urllib
from sqlalchemy import inspect, Engine
import functools

logger = logging.getLogger(__name__)


# def get_db_password(keyvault: str, secret: str) -> str:
#    """Read the db password from the keyvault"""
#    return get_secret(keyvault, secret) or ""


@functools.cache
def is_sqlite(engine: Engine) -> bool:
    """Returns True if the engine is sqlite"""
    inspector = inspect(engine)
    return "sqlite" in inspector.dialect.name.lower()


@functools.cache
def is_sqlserver(engine) -> bool:
    """Returns True if the engine is a sqlserver"""
    inspector = inspect(engine)
    return "mssql" in inspector.dialect.name.lower()


def get_url(db_engine: str | None = None) -> str:
    """Returns the db_url. If db_engine is None we read it from env variable DB_ENGINE"""
    if db_engine is None:
        db_engine = os.getenv("DB_ENGINE")

    db_server = urllib.parse.quote_plus(os.getenv("DB_SERVER", ""))
    if port_s := os.getenv("DB_PORT"):
        db_port = int(port_s)
    else:
        db_port = None

    db_username = urllib.parse.quote_plus(os.getenv("DB_USERNAME", ""))
    db_password = urllib.parse.quote_plus(os.getenv("DB_PASSWORD", ""))
    db_database = urllib.parse.quote_plus(os.getenv("DB_DATABASE", ""))
    db_driver = urllib.parse.quote_plus(os.getenv("DB_DRIVER", ""))
    # db_schema = os.getenv("DB_SCHEMA")

    if db_engine == "sqlite":
        db_database = os.getenv("DB_DATABASE", "")  # No quoting for sqlite

    if db_engine == "mssql":
        db_url = f"mssql+pyodbc://{db_username}:{db_password}@{db_server}:{db_port}/{db_database}?driver={db_driver}"
    elif db_engine == "postgresql":  # Postgres:
        db_url = f"postgresql+psycopg2://{db_username}:{db_password}@{db_server}:{db_port}/{db_database}"
    elif db_engine == "sqlite":
        db_url = f"sqlite:///{db_database}"
    else:
        raise ValueError(f"db_engine {db_engine} not supported")

    return db_url


def create_db_engine(
    db_url: str, db_schema: str | None = None, echo: bool = False
) -> Any:
    """Creates a context with an open SQLAlchemy session. Provide schema for postgresql
    to be passed as search path to postgresql"""
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
        connect_args = dict()
    if use_setinputsizes is None:
        engine = create_engine(
            db_url,
            connect_args=connect_args,
            echo=echo,
        )
    else:
        engine = create_engine(
            db_url,
            connect_args=connect_args,
            echo=echo,
            use_setinputsizes=use_setinputsizes,
        )

    return engine


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
