import logging
import time
from typing import Any, Optional, Union

import streamlit as st
from common import (
    get_participant,
    get_participants,
    get_policy_enforcer,
    set_roles_into_session_state,
)
from config import settings
from participants import (
    Participant,
    ParticipantCreate,
    ParticipantRepository,
    ParticipantState,
    ParticipantType,
    ParticipantUpdate,
    is_valid_name,
    ParticipantRelationRepository,
)
from db import get_db

logger = logging.getLogger(settings.LOGGER_NAME)


def init_session_state():
    """Initializes the session state variables (dicts) users_all_users and users_all_org_units"""
    roles = get_participants(ParticipantType.ROLE, False)
    set_roles_into_session_state(roles, "users_all_roles")


def render_roles_selectbox() -> Optional[Participant]:

    show_only_active = st.toggle(label="Show only active", value=True)
    if show_only_active:
        roles = sorted(
            [
                v["name"]
                for v in st.session_state.users_all_roles.values()
                if v["state"] == "ACTIVE"
                and v["name"] not in {"PUBLIC", "ADMINISTRATOR"}
            ]
        )
    else:
        roles = sorted(
            [
                r
                for r in st.session_state.users_all_roles.keys()
                if r not in {"PUBLIC", "ADMINISTRATOR"}
            ]
        )
    # user_collection = SREUIParticipantCollection(users)
    key = "roles_selectbox"
    selected_key = key + "_selected"
    if (
        selected_key in st.session_state
        and st.session_state[selected_key]
        and st.session_state[selected_key] in roles
    ):
        index = roles.index(st.session_state[selected_key])
    else:
        index = 0

    selected = st.selectbox(
        label="Select a role", options=roles, key=key, index=index
    )
    if selected:
        st.session_state[selected_key] = selected
        if selected_role := get_participant(
            st.session_state.users_all_roles[selected]["id"]
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


def render_create_role_form(title: str):
    """Renders the create user form and handles the submit button"""
    """Renders the create user form and handles the submit button"""
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
                        "Invalid Name. Name must be at least 2 characters long, start with a letter, "
                        + "can contain numbers, underscores and hyphens"
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
                            created_by=st.session_state.current_user[
                                "username"
                            ],
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
                        st.success(f"Role {role_name} created")
                        time.sleep(1)
                        # Clear the cache, because get_participants is cached and must be reread
                        st.cache_data.clear()
                        init_session_state()
                        st.rerun()  # to render the user selectbox new.


def render_update_role_form(selected_role: Participant):
    enforcer = get_policy_enforcer()

    disabled = not enforcer.enforce(
        st.session_state.current_user["username"], "roles", "write"
    )

    with st.form(key="update_role_form", border=False):
        if selected_role.state == ParticipantState.ACTIVE:
            index = 0
        else:
            index = 1
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

            with ParticipantRepository(get_db()) as pati_repo:

                db_changes: dict[str, Any] = dict()
                if selected_role.display_name != display_name:
                    db_changes["display_name"] = display_name
                if selected_role.description != description:
                    db_changes["description"] = description
                if state_toggle != str(selected_role.state):
                    db_changes["state"] = state_toggle
                if db_changes:
                    db_changes["updated_by"] = st.session_state.current_user[
                        "username"
                    ]
                    update = ParticipantUpdate.model_validate(db_changes)
                    try:
                        pati_repo.update(selected_role.id, update)
                    except Exception as e:
                        pati_repo.rollback()
                        logger.exception(e)
                        st.exception(e)
                        raise
                    else:
                        pati_repo.commit()
                        st.success(f"Role {selected_role.name} saved")
                        time.sleep(1)
                        get_participants.clear()  # To reread the changes.
                        init_session_state()
                        st.rerun()
                else:
                    st.info("No changes to save")


def render_roles():
    """Renders the Users dialog"""
    init_session_state()
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
    if enforcer.enforce(
        st.session_state.current_user["username"], "roles", "create"
    ):
        st.divider()
        render_create_role_form("## Create Role")
