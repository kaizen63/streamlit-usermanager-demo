"""Functions to determine the app users permissions and related functions"""

import logging
from collections.abc import Iterable
from enum import StrEnum

import casbin
import streamlit as st
from casbin.rbac import RoleManager
from config import settings
from session_user import get_session_user

logger = logging.getLogger(settings.LOGGER_NAME)


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


def get_policy_enforcer() -> casbin.Enforcer:
    """Gets the policy enforcer. On first call, store it in session_state."""
    key = "policy_enforcer"

    if enforcer := st.session_state.get(key):
        return enforcer

    logger.debug("Initializing policy enforcer")
    try:
        st.session_state[key] = casbin.Enforcer(
            "casbin/model.conf",
            "casbin/policy.csv",
        )

    except Exception as e:
        logger.exception("Failed to initialize policy enforcer", exc_info=e)
        raise

    return st.session_state[key]


# choose a short ttl during development to enable us to test the sidebar menu
# @st.cache_data(ttl=settings.POLICY_TTL, show_spinner=False)
@st.cache_data(ttl=0, show_spinner=False)
def check_access(username: str, object_: str, action: str) -> bool:
    """Check access to an object."""
    # logger.debug(f"check_access called for {username=}, {object_=}, {action=}")
    enforcer = get_policy_enforcer()
    return bool(enforcer.enforce(username, object_, action))


def user_is_administrator(username: str | None = None) -> bool:
    """
    Determines if the user has administrator privileges.

    This function checks whether a user has administrator privileges through two methods:
    1. First checks if the ADMINISTRATOR role is directly assigned in the session user's roles
    2. If not found, checks if the ADMINISTRATOR role is assigned via the policy enforcer

    Args:
        username (str | None, optional): The username to check for administrator privileges.
            If None, the current session user's username is used. Defaults to None.

    Returns:
        bool: True if the user has administrator privileges, False otherwise.

    Notes:
        This function only checks assigned roles, not effective roles that might be
        inherited through role hierarchies.

    """
    session_user = get_session_user()
    # Check direct role assignment first
    if "ADMINISTRATOR" in session_user.roles:
        return True

    username = username or session_user.username
    # Then check policy-defined roles if username is provided
    return bool(
        username
        and "ADMINISTRATOR" in get_policy_enforcer().get_roles_for_user(username),
    )


def get_role_manager() -> RoleManager:
    """Returns the role manager from the policy enforcer"""
    return get_policy_enforcer().get_role_manager()


def roles_of_role(role: str, role_manager: RoleManager) -> list[str]:
    """Returns the roles of a role. Assigned in the policy.csv"""
    return role_manager.get_roles(role)


def get_all_roles(role: str, seen: set[str], role_manager: RoleManager) -> None:
    """Get all roles of a role recursive. Drill down into each role to find other role to tole assignments"""
    if role in seen:
        return
    seen.add(role)
    for sub_role in roles_of_role(role, role_manager):
        get_all_roles(sub_role, seen, role_manager)


def get_all_roles_of_roles(roles: Iterable) -> set[str]:
    """Get all roles of a role. Drill down into each role to find other role to tole assignments"""
    role_manager = (
        get_role_manager()
    )  # Retrieve role manager once to avoid redundant calls
    all_roles: set[str] = set()
    for role in roles:
        get_all_roles(role, all_roles, role_manager)
    return all_roles


def get_user_permissions(username: str) -> dict[str, bool]:
    """Retrieve the user's permissions."""
    user_permissions = {
        perm: check_access(username, resource, action)
        for perm, (resource, action) in {
            "read_users": ("users", "read"),
            "write_users": ("users", "write"),
            "create_users": ("users", "create"),
            "read_roles": ("roles", "read"),
            "write_roles": ("roles", "write"),
            "create_roles": ("roles", "create"),
            "read_orgs": ("org_units", "read"),
            "write_orgs": ("org_units", "write"),
            "create_orgs": ("org_units", "create"),
        }.items()
    }
    logger.debug(f"Permissions of {username}: {user_permissions}")
    return user_permissions


def user_is_manager(users_title: str) -> bool:
    """
    Determines if a user is a manager based on their job title.

    This function checks if the user's title contains any management-related keywords
    that would indicate they have a management position.

    Args:
        users_title (str): The job title of the user to check.
            Can be None or empty string.

    Returns:
        bool: True if the title contains any management keywords, False otherwise.
            Always returns False if users_title is None or empty.

    Notes:
        Management is determined by the presence of keywords such as "manager",
        "director", "vp", "svp", or "chief" in the title (case-insensitive).

    """
    if not users_title:
        return False
    lower_title = users_title.lower()
    management_keywords = {
        "manager",
        "director",
        "vp",
        "svp",
        "chief",
        "senior product owner",
    }

    return any(keyword in lower_title for keyword in management_keywords)


def add_roles_to_policy_enforcer(username: str, roles: Iterable[str]) -> None:
    """Adds the (effective) roles to casbin"""
    enforcer = get_policy_enforcer()
    for r in roles:
        logger.debug(f"{username=}: Add role {r} to policy enforcer")
        enforcer.add_role_for_user(username, r)


def sync_enforcer_roles(username: str, effective_roles: set[str]) -> None:
    """
    Syncs the effective roles with the policy enforcer.

    This function updates the policy enforcer with the user's effective roles.
    and clears the access cache.

    Args:
        username: The username of the user
        effective_roles: Set of effective roles to sync with the policy enforcer

    Returns:
        None

    """
    if not username:
        return

    enforcer = get_policy_enforcer()
    casbin_roles = set(enforcer.get_roles_for_user(username))
    roles_to_add = effective_roles - casbin_roles
    roles_to_remove = casbin_roles - effective_roles
    # Do the remove first. It will also remove inherited roles
    for role in roles_to_remove:
        enforcer.delete_role_for_user(username, role)

    for role in roles_to_add:
        enforcer.add_role_for_user(username, role)
    check_access.clear()
