"""Functions called by other modules"""

import logging
from enum import StrEnum
from pathlib import Path
from typing import Any, Optional, Union, Iterable

import casbin
import streamlit as st
from config import settings

from pydantic import BaseModel, Field
from streamlit_ldap_authenticator import UserInfos

logger = logging.getLogger(settings.LOGGER_NAME)


class CurrentUser(BaseModel):
    username: str = Field(...)
    display_name: str = Field(...)
    email: str | None = Field(...)
    title: str | None = Field(default=None)
    roles: set[str] = Field(default_factory=lambda: set)
    effective_roles: set[str] = Field(default_factory=lambda: set)
    org_units: set[str] = Field(default_factory=lambda: set)


class AppRoles(StrEnum):
    """Allowed roles by this application"""

    ADMINISTRATOR = "ADMINISTRATOR"
    USER_ADMINISTRATOR = "USER_ADMINISTRATOR"
    USER_READ = "USER_READ"
    USER_WRITE = "USER_WRITE"
    ROLE_READ = "ROLE_READ"
    ROLE_WRITE = "ROLE_WRITE"
    ORG_UNIT_READ = "ORG_UNIT_READ"
    ORG_UNIT_WRITE = "ORG_UNIT_WRITE"


# A set we can use to check against
APP_ROLES = {str(member) for member in AppRoles}


class MissingStateVariableError(Exception):
    """Exception for missing variables"""

    def __init__(self, missing) -> None:
        super().__init__(f"Missing session state variable {missing}.")
        self.message: str = f"Missing session state variable {missing}."


def dequote(s):
    """
    If a string has single or double quotes around it, remove them.
    Make sure the pair of quotes match.
    If a matching pair of quotes is not found,
    or there are less than 2 characters, return the string unchanged.
    """
    if s is None or not isinstance(s, str):
        return s
    if (len(s) >= 2 and s[0] == s[-1]) and s[0] in ("'", '"'):
        return s[1:-1]
    return s


def get_st_current_user() -> CurrentUser | None:
    """Get current user from session state"""
    st_current_user = st.session_state.get("current_user", None)
    if st_current_user is None:
        return None
    return CurrentUser(**st_current_user)


def user_is_manager(user: Optional[UserInfos] = None) -> bool:
    """Checks if the user is a manager. If user is None, uses
    st.session_state.current_user.title"""
    if not user:
        current_user = get_st_current_user()
        title = current_user.title if current_user else None
    else:
        title = user.get("title", "")
    if not title:
        return False
    lower_title = title.lower()
    management_keywords = ("manager", "director", "vp", "svp", "chief")

    return any(keyword in lower_title for keyword in management_keywords)


def compare_lists(a: list[str], b: list[str]) -> tuple[list[str], list[str]]:
    """Returns a - b and b - a"""
    a_set, b_set = set(a), set(b)
    return list(a_set - b_set), list(b_set - a_set)


def compute_effective_app_roles(
    roles: Union[list[str] | set[str]],
) -> set[str]:
    """Returns the set of effective roles in this application"""

    effective_roles = list(roles.copy())

    if AppRoles.ADMINISTRATOR in roles:
        effective_roles.extend(APP_ROLES)
    return set(effective_roles)


def get_policy_enforcer() -> casbin.Enforcer:
    """Gets the policy enforcer. On first call store it in session_state"""
    var: str = "policy_enforcer"
    try:
        if var not in st.session_state or st.session_state[var] is None:
            logger.debug("Getting policy enforcer")
            enforcer = st.session_state[var] = casbin.Enforcer(
                str(Path("casbin", "model.conf")),
                str(Path("casbin", "policy.csv")),
            )
        else:
            enforcer = st.session_state[var]
    except Exception as e:
        logger.exception(e)
        raise
    else:
        return enforcer


# choose a short ttl during development to enable us to test the sidebar menu
@st.cache_data(ttl=settings.POLICY_TTL, show_spinner=False)
def check_access(username: str, object_: str, action: str) -> bool:
    """Check access to an object with streamlit caching"""
    enforcer = get_policy_enforcer()
    return enforcer.enforce(username, object_, action)


def is_administrator(username: str | None = None) -> bool:
    """Returns True if the current user is administrator by assigned roles (not effective roles)"""

    username = username or st.session_state.get("username", None)
    if "ADMINISTRATOR" in st.session_state.get("current_user", {}).get(
        "roles", []
    ):
        return True

    if (
        username
        and "ADMINISTRATOR"
        in get_policy_enforcer().get_roles_for_user(username)
    ):
        return True
    return False


def filter_list(
    items: Iterable[str],
    exclude_keywords: list[str] | tuple[str, ...] | set[str],
) -> list[str]:
    """Returns the input list where none of the items has one with a keyword in it.
    Example: input = ['SECRET_KEY', 'PASSWORD', 'DB_SERVER', 'DB_PORT']
             exclude_keywords = ("KEY", "PASSWORD")
             returns ['DB_SERVER', 'DB_PORT']
    """
    if not isinstance(exclude_keywords, (list, tuple, set)):
        raise TypeError("exclude_keywords must be a list or tuple")

    return [
        item
        for item in items
        if not any(word in item for word in exclude_keywords)
    ]
