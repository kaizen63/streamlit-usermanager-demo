"""Display and handles the main menu"""

import logging

import homepage
import streamlit as st
from about import render_about
from common import check_access
from config import settings
from debug_page import render_debug_page
from org_units import render_org_units
from roles import render_roles
from streamlit_option_menu import option_menu
from users import render_users

# from streamlit_extras.bottom_container import bottom
logger = logging.getLogger(settings.LOGGER_NAME)


def application_menu_callback(key: str) -> None:
    """Callback function for the main menu"""
    # logger.debug(f"{key=}, {st.session_state[key]}")
    if key in st.session_state:
        st.query_params["menu"] = st.session_state[key]


def get_user_permissions(username: str) -> dict[str, bool]:
    """Retrieve the user's permissions."""
    return {
        perm: check_access(username, resource, action)
        for perm, (resource, action) in {
            "read_users": ("users", "read"),
            "read_roles": ("roles", "read"),
            "read_orgs": ("org_units", "read"),
        }.items()
    }


def execute_menu_action(
    selected: str,
) -> None:
    """Executes the action corresponding to the selected menu item."""
    home_label = get_home_label()
    action_map = {
        home_label: homepage.render_homepage,
        "Users": render_users,
        "Roles": render_roles,
        "Orgs": render_org_units,
        "About": render_about,
        "Debug": render_debug_page,
    }

    if action := action_map.get(selected):
        action()


def get_home_label() -> str:
    return (
        f"Home[{st.session_state.env}]"
        if st.session_state.get("env", "PROD") != "PROD"
        else "Home"
    )


def generate_menu_items(
    permissions: dict[str, bool],
) -> tuple[tuple[str], tuple[str]]:
    """Generate menu options and corresponding icons based on permissions."""
    home_label = get_home_label()

    menu_items = [
        (home_label, "house") if permissions["read_users"] else None,
        ("Users", "people") if permissions["read_users"] else None,
        ("Roles", "mortarboard") if permissions["read_roles"] else None,
        ("Orgs", "building") if permissions["read_orgs"] else None,
        ("About", "info-circle"),
        ("Debug", "bug") if st.query_params.get("debug", "0") == "1" else None,
    ]

    # Remove None values and unpack into separate lists
    # options = [item[0] for item in menu_items if item]
    # icons = [item[1] for item in menu_items if item]
    # return options, icons
    options, icons = zip(*[item for item in menu_items if item], strict=False)
    return tuple(options), tuple(icons)


def render_main_menu() -> None:
    """Renders the main menu of the application"""
    title = st.query_params.get("title")

    user = st.session_state["current_user"]
    username = user["username"]
    effective_roles = user["effective_roles"]

    logger.debug(f"User {username}. Effective roles: {effective_roles}")

    if title:
        user["title"] = title

    permissions = get_user_permissions(username)
    logger.debug(f"User {username} has these permissions: {permissions}")
    options, icons = generate_menu_items(permissions)

    # Determine menu selection
    menu_selection = st.query_params.get("menu")
    index = options.index(menu_selection) if menu_selection in options else 0
    st.query_params["menu"] = options[index]

    selected = option_menu(
        menu_title=None,
        options=options,
        icons=icons,
        menu_icon="cast",
        orientation="horizontal",
        default_index=index,
        key="application_menu",
        manual_select=(0 if menu_selection and menu_selection not in options else None),
        on_change=application_menu_callback,
    )

    logger.info(f"User {username} selected menu: {selected}")
    # Execute the selected menu action
    execute_menu_action(selected)
