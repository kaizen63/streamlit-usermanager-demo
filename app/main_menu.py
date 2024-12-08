"""Display and handles the main menu"""

import json
import logging
import os

import homepage
import streamlit as st
from about import render_about
from common import check_access, get_policy_enforcer, get_st_current_user
from config import settings
from org_units import render_org_units
from roles import render_roles
from streamlit_option_menu import option_menu
from users import render_users

# from streamlit_extras.bottom_container import bottom
logger = logging.getLogger(settings.LOGGER_NAME)


def application_menu_callback(key: str):
    """Callback function for the main menu"""
    # logger.debug(f"{key=}, {st.session_state[key]}")
    if key in st.session_state:
        st.query_params["menu"] = st.session_state[key]


def render_main_menu() -> None:
    """Renders the main menu of the application"""
    # icons: https://icons.getbootstrap.com/
    debug_on: bool = st.query_params.get("debug", "0") == "1"
    # For debugging. Disable in prod
    title = st.query_params.get("title")

    enforcer = get_policy_enforcer()

    if title:
        st.session_state.current_user["title"] = title
    current_user = get_st_current_user()
    if not current_user:
        return
    username = current_user.username
    current_user_roles = enforcer.get_roles_for_user(username)
    logger.debug(
        f'User {username}. current roles: {", ".join(current_user_roles)}, effective_roles={current_user.effective_roles}'
    )

    options = []
    icons = []
    home = "Home"
    options.append(home)
    icons.append("house")

    if check_access(username, "users", "read"):
        options.append("Users")
        icons.append("people")
    if check_access(username, "roles", "read"):
        options.append("Roles")
        icons.append("mortarboard")
    if check_access(username, "org_units", "read"):
        options.append("Orgs")
        icons.append("building")

    options.extend(["About"])
    icons.extend(["info-circle"])

    if debug_on:
        options.append("Debug")
        icons.append("bug")
        os.environ["POLICY_TTL"] = "0"
        logger.info(f"Debug on: Set POLICY_TTL to: {settings.POLICY_TTL}")
    else:
        logger.debug(f"POLICY_TTL: {settings.POLICY_TTL}")

    manual_select = None
    if menu := st.query_params.get("menu"):
        try:
            index = options.index(menu)
        except ValueError:
            index = 0
            manual_select = 0
    else:
        index = 0
    st.query_params["menu"] = options[index]
    # manual_select is overwriting the index
    selected = option_menu(
        menu_title=None,  # "Main Menu",
        options=options,
        icons=icons,
        menu_icon="cast",
        orientation="horizontal",
        default_index=index,
        key="application_menu",
        manual_select=manual_select,
        on_change=application_menu_callback,
    )

    logger.debug(f"User {username} selected menu: {selected}")
    match selected:
        case _ if selected.startswith("Home"):
            homepage.render_homepage()

        case "Users":
            if check_access(username, "users", "read"):
                render_users()
            else:
                st.error("You are not authorized to access this page")
                st.stop()
        case "Roles":
            if check_access(username, "roles", "read"):
                render_roles()
            else:
                st.error("You are not authorized to access this page")
                st.stop()

        case "Orgs":
            if check_access(username, "org_units", "read"):
                render_org_units()
            else:
                st.error("You are not authorized to access this page")
                st.stop()

        case "About":
            render_about()

        case "Debug":
            st.write("## Session State")
            session_state = dict(st.session_state.items())
            del session_state["cookies"]
            st.json(
                body=json.dumps(
                    session_state,
                    indent=4,
                    sort_keys=True,
                    ensure_ascii=False,
                    default=str,
                ),
                expanded=False,
            )

        case _:
            pass
