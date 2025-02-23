"""Handles the Roles page"""

import logging
import time
from typing import Optional, Union

import streamlit as st
from common import check_access, get_policy_enforcer, safe_index
from config import settings
from db import get_db
from participant_utilities import (
    get_participant_by_name,
    get_roles,
)
from participants import (
    Participant,
    ParticipantCreate,
    ParticipantRelationRepository,
    ParticipantRepository,
    ParticipantState,
    ParticipantType,
    ParticipantUpdate,
    is_valid_name,
)

logger = logging.getLogger(settings.LOGGER_NAME)


def render_roles_selectbox() -> Optional[Participant]:
    """Renders the roles select box"""
    show_only_active = st.toggle(label="Show only active", value=True)
    current_user = st.session_state.current_user["username"]
    exclude_roles = (
        {"PUBLIC"}
        if check_access(current_user, "all_roles", "read")
        else {"PUBLIC", "ADMINISTRATOR"}
    )

    all_roles: list[Participant] = get_roles(only_active=show_only_active)
    roles = sorted(
        [role.name for role in all_roles if role.name not in exclude_roles]
    )
    key = "roles_selectbox"
    selected_key = f"{key}_selected"
    index = safe_index(roles, selected_key)
    index = safe_index(roles, st.session_state.get(selected_key), 0)

    selected = st.selectbox(
        label="Select a role", options=roles, key=key, index=index
    )
    if selected:
        st.session_state[selected_key] = selected
        if selected_role := get_participant_by_name(
            selected, ParticipantType.ROLE, include_relations=True
        ):
            return selected_role
        else:
            st.error(f"Selected role not found. {selected} ")
            # Remove the user from the session_state.user_users
            st.session_state.users_all_org_units.pop(selected)
            st.stop()

    return None


def render_participants_granted_this_role(
    selected_role: Participant, participant_type: ParticipantType
) -> list[str]:
    """Render the participants the selected role is granted to."""
    with ParticipantRelationRepository(get_db()) as repo:
        users_granted_this_role = repo.get_reverse(
            selected_role.id, ("GRANT",)
        )
        if users_granted_this_role:
            options = [
                m.participant.display_name
                for m in users_granted_this_role
                if m.participant.participant_type == participant_type
            ]
        else:
            options = []
    key = f"granted_roles_to_{participant_type}"
    if participant_type == ParticipantType.HUMAN:
        prefix = "Users"
    elif participant_type == ParticipantType.ORG_UNIT:
        prefix = "Organizations"
    else:
        prefix = "Participants"

    selected = st.multiselect(
        f"{prefix} granted this role to [{len(options)}]:",
        options=options,
        default=options,
        disabled=True,
        key=key,
    )
    return selected


def render_create_role_form(title: str) -> None:
    """Renders the create role form and handles the submit button"""
    with st.form(key="create_role_form", clear_on_submit=False):
        st.write(title)
        role_name = st.text_input(
            "Name",
            help="Role Name",
            placeholder="",
        )
        display_name = st.text_input("Display Name", placeholder="", help="")
        description = st.text_input(
            "Description (Optional)", placeholder="", help=""
        )

        if st.form_submit_button("Create"):
            if not display_name or not role_name:
                st.error("Please fill in all fields")
            else:
                if not is_valid_name(role_name.strip()):
                    st.error(
                        "Invalid Name. Name must be at least 2 characters long, start with a letter,"
                        + " can contain numbers, underscores and hyphens"
                    )
                    st.stop()

                role_name = role_name.upper()
                with ParticipantRepository(get_db()) as pati_repo:
                    exists: Union[bool | str] = pati_repo.exists(
                        "name", role_name, ParticipantType.ROLE
                    )
                    if exists:
                        if exists == ParticipantState.TERMINATED:
                            st.error(
                                f"Role {role_name!a} already exists but is not active"
                            )
                        else:
                            st.error(f"Role {role_name!a} already exists")

                        return
                    exists = pati_repo.exists(
                        "display_name", display_name, ParticipantType.ROLE
                    )
                    if exists:
                        if exists == ParticipantState.TERMINATED:
                            st.error(
                                f"Role with the same display name: {display_name!a} already exists but is not active"
                            )
                        else:
                            st.error(
                                f"Role with the same display name: {display_name!a} already exists"
                            )
                        return
                    try:
                        create = ParticipantCreate(
                            name=role_name,
                            display_name=display_name,
                            description=description,
                            created_by=st.session_state.username,
                            participant_type=ParticipantType.ROLE,
                        )
                        _ = pati_repo.create(create)

                        # Now add him to the session state.
                    except Exception as e:
                        logger.exception(f"Role creation failed: {e}")
                        st.error("Oops that went wrong")
                        pati_repo.rollback()
                    else:
                        pati_repo.commit()
                        get_roles.clear()
                        st.success(f"Role {role_name} created")
                        time.sleep(1)
                        st.rerun()  # to render the user selectbox new.


def render_update_role_form(selected_role: Participant) -> None:
    """Renders the role update dialog"""
    enforcer = get_policy_enforcer()
    disabled = not enforcer.enforce(
        st.session_state.username, "roles", "write"
    )

    with st.form(key="update_role_form", border=False):
        index = 0 if selected_role.state == ParticipantState.ACTIVE else 1

        state_toggle = st.radio(
            label="Status",
            options=["ACTIVE", "TERMINATED"],
            #  captions=["Active", "Disabled"],
            horizontal=True,
            index=index,
            disabled=disabled,
        )
        display_name = st.text_input(
            label="Display Name",
            value=selected_role.display_name,
            disabled=disabled,
        )
        description = st.text_input(
            label="Description",
            value=selected_role.description,
            disabled=disabled,
        )
        if st.form_submit_button("Save", disabled=disabled):
            if len(display_name) == 0:
                st.error("Display name cannot be empty")
                st.stop()
            db_changes = {
                "display_name": (
                    display_name
                    if selected_role.display_name != display_name
                    else None
                ),
                "description": (
                    description
                    if selected_role.description != description
                    else None
                ),
                "state": (
                    state_toggle
                    if state_toggle != str(selected_role.state)
                    else None
                ),
            }
            db_changes = {k: v for k, v in db_changes.items() if v is not None}
            if db_changes:
                db_changes["updated_by"] = st.session_state.username
                update = ParticipantUpdate.model_validate(db_changes)

                with ParticipantRepository(get_db()) as pati_repo:
                    try:
                        pati_repo.update(selected_role.id, update)
                    except Exception as e:
                        pati_repo.rollback()
                        logger.exception(e)
                        st.exception(e)
                        raise
                    else:
                        pati_repo.commit()
                        get_roles.clear()
                        get_participant_by_name.clear()
                        st.success(f"Role {selected_role.name} saved")
                        time.sleep(1)
                        st.rerun()
            else:
                st.info("No changes to save")


def render_roles() -> None:
    """Renders the Users dialog"""
    with st.container(border=True):
        st.write("## Roles")
        selected_role = render_roles_selectbox()
        if not selected_role:
            st.stop()

        render_update_role_form(selected_role)
        render_participants_granted_this_role(
            selected_role, ParticipantType.HUMAN
        )
        render_participants_granted_this_role(
            selected_role, ParticipantType.ORG_UNIT
        )

    enforcer = get_policy_enforcer()
    if enforcer.enforce(st.session_state.username, "roles", "create"):
        st.divider()
        render_create_role_form("## Create Role")
