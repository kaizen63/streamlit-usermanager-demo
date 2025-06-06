import logging
from dataclasses import asdict, dataclass, field

import streamlit as st
from config import settings

logger = logging.getLogger(settings.LOGGER_NAME)

SESSION_USER_KEY = "session_user"


@dataclass
class SessionUser:
    """
    Current Application User in session_state.

    Represents the currently logged-in user with their attributes and permissions.

    Attributes:
        username: User's login name
        display_name: User's display name
        department: User's department
        email: User's email address
        title: User's job title
        roles: Set of roles assigned to the user
        effective_roles: Set of effective roles (including inherited roles)
        org_units: Set of organizational units the user belongs to

    """

    username: str = field(default="")
    display_name: str = field(default="")
    department: str = field(default="")
    email: str | None = field(default=None)
    title: str | None = field(default=None)
    roles: set[str] = field(default_factory=set)
    effective_roles: set[str] = field(default_factory=set)
    org_units: set[str] = field(default_factory=set)
    permissions: dict[str, bool] = field(default_factory=dict)

    def update_session_state(self) -> None:
        """
        Updates the session state to reflect the current user.

        Stores the current user information in  st.session state.
        """
        st.session_state[SESSION_USER_KEY] = asdict(self)


def get_session_user() -> SessionUser:
    """
    Returns the current user from the session state or an empty SessiontUser object.

    Returns:
        SessionUser: Either the user from session state or a new empty user object

    """
    if SESSION_USER_KEY in st.session_state:
        return SessionUser(**st.session_state[SESSION_USER_KEY])
    return SessionUser()
