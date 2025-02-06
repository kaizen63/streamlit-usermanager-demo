"""
Does the setup of the logging module.
"""

import datetime as dt
import json
import logging
import logging.config
import os
import time
from pathlib import Path

import streamlit as st

# import coloredlogs
import yaml
from typing_extensions import override


class LogLevelInvalidError(Exception):
    pass


def dequote(s):
    """
    If a string has single or double quotes around it, remove them.
    Make sure the pair of quotes match.
    If a matching pair of quotes is not found,
    or there are less than 2 characters, return the string unchanged.
    """
    if s is None:
        return s
    if (len(s) >= 2 and s[0] == s[-1]) and s.startswith(("'", '"')):
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
    # Check if we have a logs directory:
    # if Path("../logs").exists() is False:
    #    Path("../logs").mkdir()

    file_path = Path(default_path)
    env_path = dequote(os.getenv(env_key, None))
    if env_path:
        file_path = Path(env_path)

    log_path = Path(Path(file_path.absolute()).parent.parent, "logs")
    if not log_path.exists():
        log_path.mkdir()

    if file_path.exists():
        with open(file_path, "r") as f:
            try:
                config = yaml.safe_load(f.read())
            except Exception as e:
                print(f"Failed to process yaml in {file_path} - Error: {e}")
            try:
                logging.config.dictConfig(config)
            except Exception as e:
                print(
                    f"Failed to setup logging with this config: {config} - Error: {e}"
                )
                logging.basicConfig(level=default_level)

    else:
        logging.basicConfig(level=default_level)
    # coloredlogs.install(level=default_level)
    if log_in_utc:
        logging.Formatter.converter = time.gmtime

    return None


def get_level(level: str) -> int:
    """Returns the log level number for a loglevel string string"""
    level_name_mapping = logging.getLevelNamesMapping()
    if level := level_name_mapping.get(level.upper()):
        return level

    raise LogLevelInvalidError(f"Not a valid log level: {level}")


def set_log_level_from_env(
    logger_name: str,
    env_key: str = "LOGGING_LOG_LEVEL",
) -> None:
    """Sets the loglevel of the logger and root logger to a level, if not already set
    env_key: The env variable holding the desired log level
    """
    logger = logging.getLogger(logger_name)
    if logger.level == logging.NOTSET:
        log_level = dequote(os.getenv(env_key, ""))
        if log_level:
            logger.info(f"Set loglevel to {log_level}")
            level = get_level(log_level)
            logger.setLevel(level)
            if logger.root:
                logger.root.setLevel(level)
    return


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
    lower casing the name.
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
    ):
        super().__init__()
        self.fmt_keys = fmt_keys if fmt_keys is not None else {}

    @override
    def format(self, record: logging.LogRecord) -> str:
        message = self._prepare_log_dict(record)
        return json.dumps(message, default=str)

    def _prepare_log_dict(
        self, record: logging.LogRecord
    ) -> dict[str, str | None]:
        always_fields = {
            "message": record.getMessage(),
            "timestamp": dt.datetime.fromtimestamp(
                record.created, tz=dt.timezone.utc
            ).isoformat(),
        }
        if st.session_state.get("current_user"):
            user_info = {
                "username": st.session_state.current_user["username"],
                "user_display_name": st.session_state.current_user[
                    "display_name"
                ],
            }
            always_fields.update(user_info)
        logger_env = {
            k.lstrip("LOGGER_").lower(): v
            for k, v in os.environ.items()
            if k.startswith("LOGGER_")
        }
        always_fields.update(logger_env)

        if record.exc_info is not None:
            always_fields["exc_info"] = self.formatException(record.exc_info)

        if record.stack_info is not None:
            always_fields["stack_info"] = self.formatStack(record.stack_info)

        message = {
            key: (
                msg_val
                if (msg_val := always_fields.pop(val, None)) is not None
                else getattr(record, val)
            )
            for key, val in self.fmt_keys.items()
        }
        message.update(always_fields)
        # here the extra args are added
        for key, val in record.__dict__.items():
            if key not in LOG_RECORD_BUILTIN_ATTRS:
                message[key] = val

        return message
