import logging
from typing import TYPE_CHECKING, Literal

import streamlit as st
from common import (
    AppRoles,
    check_access,
    get_all_roles_of_roles,
    get_policy_enforcer,
    get_user_permissions,
    is_administrator,
)
from config import settings
from session_user import get_session_user

if TYPE_CHECKING:
    from streamlit.connections import SQLConnection
from streamlit_ldap_authenticator import Authenticate
from streamlit_rsa_auth_ui import SignoutEvent

# from streamlit_extras.bottom_container import bottom
logger = logging.getLogger(settings.LOGGER_NAME)


def role_checkbox_callback(role: str, key: str) -> None:
    # logger.debug(f"Callback: {role=}, {key=}")
    if key not in st.session_state:
        return
    # To for check_access to reread.
    check_access.clear()
    if not (session_user := get_session_user()):
        return
    enforcer = get_policy_enforcer()
    if st.session_state[key] is True:
        for related_role in get_all_roles_of_roles({role}):
            session_user.effective_roles.add(related_role)
        enforcer.add_role_for_user(session_user.username, role)

    else:
        if role != AppRoles.ADMINISTRATOR:
            related_roles = get_all_roles_of_roles({role})
            for related_role in related_roles:
                session_user.effective_roles.discard(related_role)
        else:
            session_user.effective_roles.discard(role)
        enforcer.delete_role_for_user(session_user.username, role)
        # roles = enforcer.get_roles_for_user(session_user.username)
        # print(roles)

    check_access.clear()
    session_user.permissions = get_user_permissions(session_user.username)
    session_user.update_session_state()
    return


def render_user_roles(
    title: str, all_roles: list[str], users_effective_roles: set[str]
) -> None:
    """Render the tickboxes with user roles on the sidebar"""
    st.write(title)
    if "PUBLIC" in all_roles:
        all_roles.remove("PUBLIC")
    for _i, role in enumerate(all_roles):
        key = f"sidebar_roles_{role}"
        value = role in users_effective_roles
        st.checkbox(
            role,
            value=value,
            disabled=False,
            on_change=role_checkbox_callback,
            args=(role, key),
            key=key,
        )


def render_sidebar(auth: Authenticate) -> None:
    """Render the sidebar"""

    def render_logout_form(user: str) -> None:
        """Renders the logout form"""
        (
            auth.createLogoutForm(
                config={
                    "message": "",
                    "title": {
                        "text": f"Welcome {user}",
                        "size": "small",
                    },
                },
                callback=signout_callback,
            )
            if auth
            else st.write(f"Welcome {user}")
        )

    session_user = get_session_user()
    if not session_user:
        return
    with st.sidebar:
        # st.sidebar.title(f"Welcome {user['displayName']}")
        # display_user = get_st_session_user()
        st.write("### Welcome: " + get_session_user().display_name)
        # render_logout_form()
        st.divider()

        # Use a new policy enforcer, so the files are read again. We need to know
        # when a policy has changed. e.g. when the SUPERADMIN is granted and revoked
        if is_administrator(session_user.username):
            user_roles: list[str] = sorted(get_all_roles_of_roles(session_user.roles))
            effective_roles = session_user.effective_roles

            render_user_roles("Your roles:", user_roles, effective_roles)

            st.divider()
            # because I am too lazy to type the param in the url. Added this shortcut
            if st.checkbox(
                "Debug Menu", value=st.query_params.get("debug", "0") == "1"
            ):
                st.query_params["debug"] = "1"
            elif st.query_params.get("debug"):
                del st.query_params["debug"]

            if is_administrator(st.session_state.username) and st.button(
                "Clear caches"
            ):
                logger.info("Clear caches was requested via user interface.")
                st.cache_data.clear()


def signout_callback(event: SignoutEvent) -> Literal["cancel", None]:
    if event.event == "signout":
        logger.info(
            f"User {st.session_state.get('user_display_name', '?')} ({st.session_state.get('username', '?')}) logged out."
        )
        st.session_state["username"] = ""
        st.session_state["user_display_name"] = ""
        st.session_state["session_user"] = {}
        st.session_state["must_register"] = False
        st.session_state["policy_enforcer"] = None

        connection: SQLConnection | None = st.session_state.get("db_connection")
        if connection:
            connection.engine.dispose()
            st.session_state["db_connection"] = None

        st.cache_data.clear()
        for key in st.session_state:
            del st.session_state[key]
    return None  # return "cancel" on error
