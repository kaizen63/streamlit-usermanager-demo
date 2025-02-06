""" Functions called by other modules """

import logging
from enum import StrEnum
from pathlib import Path
from typing import Any, Optional, Union

import casbin
import streamlit as st
from config import settings
from participants import Participant, ParticipantRepository, ParticipantType
from pydantic import BaseModel, Field
from streamlit_ldap_authenticator import UserInfos
from db import get_db


logger = logging.getLogger(settings.LOGGER_NAME)


class CurrentUser(BaseModel):
    username: str = Field(...)
    display_name: str = Field(...)
    email: str = Field(...)
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
    if (len(s) >= 2 and s[0] == s[-1]) and s.startswith(("'", '"')):
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
        user = get_st_current_user()

    if not user or not user.get("title"):
        return False

    lower_title = user["title"].lower()
    management_keywords = ("manager", "director", "vp", "svp", "chief")

    return any(keyword in lower_title for keyword in management_keywords)


def set_users_into_session_state(
    users: list[Participant], state_variable: str
) -> None:
    """Store the id, name and description in st.session_state.users_all_users
    Key is the description because that one is used in the select box"""
    data: dict[str, dict[str, Any]] = {}
    for u in users:
        data[u.display_name] = {
            "id": u.id,
            "name": u.name,
            "display_name": u.display_name,
            "state": u.state,
            "roles": [r.name for r in u.roles],
            "org_units": [o.name for o in u.org_units],
        }
    st.session_state[state_variable] = data


def set_org_units_into_session_state(
    org_units: list[Participant], state_variable: str
) -> None:
    """Store the id, name and description in st.session_state.users_user
    Key is the description because that one is used in the select box"""
    data: dict[str, dict[str, Any]] = {}
    for ou in org_units:
        data[ou.display_name] = {
            "id": ou.id,
            "name": ou.name,
            "display_name": ou.display_name,
            "state": ou.state,
        }
    st.session_state[state_variable] = data


def set_roles_into_session_state(
    roles: list[Participant], state_variable: str
) -> None:
    """Store the id, name and description in st.session_state.users_user
    Key is the description because that one is used in the select box"""
    data: dict[str, dict[str, Any]] = {}
    for r in roles:
        data[r.name] = {
            "id": r.id,
            "name": r.name,
            "display_name": r.display_name,
            "state": r.state,
        }
    st.session_state[state_variable] = data


@st.cache_data(ttl=600, show_spinner="Loading data...")
def get_participants(
    participant_type: str, only_active: bool
) -> list[Participant]:
    """Get a list of all participants"""
    logger.debug(f"Get participants of type {participant_type} from database")
    with ParticipantRepository(get_db()) as pati_repo:
        users: list[Participant] = pati_repo.get_all(
            participant_type, include_relations=False, only_active=only_active
        )
        return users


@st.cache_data(ttl=600, show_spinner="Loading data...")
def get_all_users(only_active: bool = False) -> list[Participant]:
    """Get all participants"""
    with ParticipantRepository(get_db()) as pati_repo:
        all_participants: list[Participant] = pati_repo.get_all(
            "HUMAN",
            only_active=only_active,
            include_relations=False,
        )
        return all_participants


def get_participant(
    pati_id: int, include_relations: bool = True, include_proxies: bool = True
) -> Optional[Participant]:
    """Get a participant by its id. Can be of all types of participants"""

    with ParticipantRepository(get_db()) as pati_repo:
        participant: Optional[Participant] = pati_repo.get_by_id(
            pati_id,
            include_relations=include_relations,
            include_proxies=include_proxies,
        )
        return participant


@st.cache_data(ttl=600, show_spinner=False)
def get_participant_by_name(
    name: str, participant_type: ParticipantType
) -> Optional[Participant]:
    """Returns the participant who maintained the change or created the app"""
    try:
        with ParticipantRepository(get_db()) as repo:
            pati = repo.get_by_name(name, participant_type)
    except Exception as e:
        logger.exception(f"Cannot find {name} in users {e}")
        return None
    else:
        return pati


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
    if not username:
        username = st.session_state.get("username", None)

    if (
        "current_user" in st.session_state
        and "ADMINISTRATOR" in st.session_state.current_user.get("roles", [])
    ):
        return True
    if username:
        enforcer = get_policy_enforcer()
        if "ADMINISTRATOR" in enforcer.get_roles_for_user(username):
            return True
    return False


@st.cache_data(ttl=600, show_spinner=False)
def get_maintainer(name: str | None) -> Optional[Participant]:
    """Returns the participant who maintained the change or created the app"""
    if not name:
        return None
    return get_participant_by_name(name, ParticipantType.HUMAN)
