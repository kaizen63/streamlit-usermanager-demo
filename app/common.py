"""Common functions called by other modules."""

import logging
from collections.abc import Iterable

# from pydantic import BaseModel, Field
from config import settings

logger = logging.getLogger(settings.LOGGER_NAME)


class MissingStateVariableError(Exception):
    """Exception for missing variables"""

    def __init__(self, missing: str) -> None:
        super().__init__(f"Missing session state variable {missing}.")
        self.message: str = f"Missing session state variable {missing}."


def dequote(s: str) -> str:
    """
    If a string has single or double quotes around it, remove them.

    Make sure the pair of quotes match.
    If a matching pair of quotes is not found,
    or there are less than 2 characters, return the string unchanged.
    """
    if s is None or not isinstance(s, str):
        return s
    if (len(s) >= 2 and s[0] == s[-1]) and s[0] in ("'", '"'):  # noqa: PLR2004
        return s[1:-1]
    return s


def compare_lists(a: list[str], b: list[str]) -> tuple[list[str], list[str]]:
    """Returns a - b and b - a"""
    a_set, b_set = set(a), set(b)
    return list(a_set - b_set), list(b_set - a_set)


def filter_list(
    items: Iterable[str],
    exclude_keywords: list[str] | tuple[str, ...] | set[str],
) -> list[str]:
    """
    Returns the input list where none of the items has one with a keyword in it.

    Example: input = ['SECRET_KEY', 'PASSWORD', 'DB_SERVER', 'DB_PORT']
             exclude_keywords = ("KEY", "PASSWORD")
             returns ['DB_SERVER', 'DB_PORT']
    """
    if not isinstance(exclude_keywords, list | tuple | set):
        raise TypeError("exclude_keywords must be a list or tuple")

    return [
        item for item in items if not any(word in item for word in exclude_keywords)
    ]


def safe_index[T](
    iterable: Iterable[T], item: T, default: int | None = None
) -> int | None:
    return next((i for i, x in enumerate(iterable) if x == item), default)
