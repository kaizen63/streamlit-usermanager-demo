"""Provides the who_called_me function"""

from inspect import stack


def who_called_me(stacklevel: int = 0) -> str:
    """Returns caller information in a string"""
    try:
        caller = stack()[stacklevel + 2]
    except IndexError:
        return ""
    else:
        return f"{caller.filename}:{caller.lineno} - {caller.function}"


def who_called_me2(stacklevel: int = 0) -> tuple[str, int, str]:
    """Returns callers filename (full path), lineno, function name"""
    try:
        caller = stack()[stacklevel + 2]
    except IndexError:
        return ("unknown", 0, "unknown")
    else:
        return caller.filename, caller.lineno, caller.function
