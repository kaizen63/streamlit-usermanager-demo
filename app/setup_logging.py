"""Does the setup of the logging module."""

import datetime as dt
import json
import logging
import logging.config
import os
import time
from pathlib import Path
from typing import cast, override

import streamlit as st

# import coloredlogs
import yaml


class LogLevelInvalidError(Exception):
    pass


def dequote(s: str | None) -> str | None:
    """
    If a string has single or double quotes around it, remove them.

    Make sure the pair of quotes match.
    If a matching pair of quotes is not found,
    or there are less than 2 characters, return the string unchanged.
    """
    if s is None:
        return s
    if (len(s) >= 2 and s[0] == s[-1]) and s.startswith(("'", '"')):  # noqa: PLR2004
        return s[1:-1]
    return s


def setup_logging(
    default_path: str | Path = "logging-conf.yaml",
    default_level: int = logging.INFO,
    env_key: str = "LOGGING_CONFIG",
    log_in_utc: bool = True,
) -> None:
    """
    Configure logging from a yaml dict.

    Environment has priority over default_path
    Args:
        default_path: The default configuration file in yaml format.
        default_level: The default logging level if there is no config file
        env_key: The env variable pointing to the config file
        log_in_utc: Flag indicating if the timestamps should be in UTC.

    Returns:
        None

    """
    file_path = (
        Path(cast("str", dequote(os.getenv(env_key, str(default_path)))))
        .expanduser()
        .resolve()
    )

    log_path = file_path.parents[1] / "logs"
    log_path.mkdir(exist_ok=True, parents=True)

    if not file_path.exists():
        logging.basicConfig(level=default_level)
        return
    try:
        with file_path.open() as f:
            config = yaml.safe_load(f)
        logging.config.dictConfig(config)
    except (yaml.YAMLError, OSError) as e:
        logging.error(f"Failed to process YAML file {file_path}: {e}")  # noqa: LOG015
        logging.basicConfig(level=default_level)
    except Exception as e:
        logging.error(  # noqa: LOG015
            f"Failed to set up logging with config {file_path}: {e}"
        )
        logging.basicConfig(level=default_level)

    if log_in_utc:
        logging.Formatter.converter = time.gmtime

    return


def get_level(level: str) -> int:
    """Returns the log level number for a log level string."""
    level_number = logging.getLevelNamesMapping().get(level.upper())
    if level_number is not None:
        return level_number
    raise LogLevelInvalidError(f"Not a valid log level: {level}")


def set_log_level_from_env(
    logger_name: str, env_key: str = "LOGGING_LOG_LEVEL"
) -> None:
    """
    Sets the log level of the specified logger and root logger based on an environment variable.

    Args:
        logger_name: Name of the logger to update.
        env_key: The environment variable holding the desired log level.

    """
    logger = logging.getLogger(logger_name)

    if logger.level != logging.NOTSET:
        return  # Skip if already set

    log_level = dequote(os.getenv(env_key, "") or None)
    if not log_level:
        return  # No log level provided

    logger.info(f"Setting log level to {log_level}")

    try:
        level = get_level(log_level)
        logger.setLevel(level)
        logger.root.setLevel(level)  # Directly set root level
    except LogLevelInvalidError as e:
        logger.error(f"Invalid log level from {env_key}: {log_level} - {e}")


LOG_RECORD_BUILTIN_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
}


class MyJSONFormatter(logging.Formatter):
    """
    Custom formatter to format the log records as JSON.

    Is reading environment variables starting with LOGGER_ and adds them to the log but removing LOGGER_ and
    lower case the name.

    Examples:
        - LOGGER_APPLICATIONNAME
        - LOGGER_SERVICE

    See here: https://github.com/mCodingLLC/VideosSampleCode/tree/master/videos/135_modern_logging
    and here: https://www.youtube.com/watch?v=9L77QExPmI0

    """

    def __init__(
        self,
        *,
        fmt_keys: dict[str, str] | None = None,
    ) -> None:
        super().__init__()
        self.fmt_keys = fmt_keys or {}

    @override
    def format(self, record: logging.LogRecord) -> str:
        message = self._prepare_log_dict(record)
        return json.dumps(message, default=str)

    def _prepare_log_dict(self, record: logging.LogRecord) -> dict[str, str | None]:
        log_data = {
            "message": record.getMessage(),
            "timestamp": dt.datetime.fromtimestamp(
                record.created, tz=dt.UTC
            ).isoformat(),
            "application_name": st.session_state.get("application_name", ""),
        }
        if st.session_state.get("current_user"):
            log_data.update(
                {
                    "username": st.session_state.current_user["username"],
                    "user_display_name": st.session_state.current_user["display_name"],
                }
            )

            # Add environment variables starting with LOGGER_
            log_data.update(
                {
                    k[7:].lower(): v
                    for k, v in os.environ.items()
                    if k.startswith("LOGGER_")
                }
            )

        if record.exc_info is not None:
            log_data["exc_info"] = self.formatException(record.exc_info)

        if record.stack_info is not None:
            log_data["stack_info"] = self.formatStack(record.stack_info)

        # Include formatted keys from fmt_keys
        formatted_keys = {
            key: (
                msg_val
                if (msg_val := log_data.pop(val, None)) is not None
                else getattr(record, val)
            )
            for key, val in self.fmt_keys.items()
        }
        log_data.update(formatted_keys)

        # Add extra attributes from the log record
        extra_attributes = {
            key: val
            for key, val in record.__dict__.items()
            if key not in LOG_RECORD_BUILTIN_ATTRS
        }
        log_data.update(extra_attributes)

        return log_data
