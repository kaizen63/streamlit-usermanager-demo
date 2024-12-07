import logging
import time
from typing import Any, Optional, Union

import streamlit as st
from common import (
    compare_lists,
    get_participant,
    get_participants,
    get_policy_enforcer,
    set_org_units_into_session_state,
    set_roles_into_session_state,
)
from config import settings
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
from db import get_db
from users import add_roles, delete_roles

logger = logging.getLogger(settings.LOGGER_NAME)


def init_session_state():
    """Initializes the session state variables (dicts) users_all_users and users_all_org_units"""
    org_units = get_participants(ParticipantType.ORG_UNIT, False)
    set_org_units_into_session_state(org_units, "users_all_org_units")
    roles = get_participants(ParticipantType.ROLE, True)
    set_roles_into_session_state(roles, "users_all_roles")


def render_roles_granted_to_org(
    title: str, selected_org: Participant, disabled: bool
) -> list[str]:
    """Render the roles multiselect"""
    st.write(title)
    selected_org_roles: Optional[set[str]] = set(
        [r.name for r in selected_org.roles if r.name != "PUBLIC"]
    )

    key = "org_unit_roles_multiselect"
    dis = disabled or (
        True if (selected_org.state == ParticipantState.TERMINATED) else False
    )
    roles = get_participants(ParticipantType.ROLE, False)
    options = [
        r.name for r in roles if r.name != "PUBLIC"
    ]  # remove the ones we  do not want

    selected_roles = st.multiselect(
        f"Roles granted to this Org [{len(selected_org_roles)}]",
        options=options,
        default=None if not selected_org_roles else selected_org_roles,
        key=key,
        disabled=dis,
    )
    return selected_roles


def render_users_of_org(
    title: str, selected_org: Participant, disabled: bool
) -> list[str]:
    """Render the users of this org but don't let them change yet"""
    st.write(title)

    # get the users connected to this org
    selected_options = []
    with ParticipantRelationRepository(get_db()) as repo:
        members_of_org = repo.get_reverse(selected_org.id, ("MEMBER OF",))
        if members_of_org:
            selected_options = [
                m.participant.display_name
                for m in members_of_org
                if m.participant.participant_type == ParticipantType.HUMAN
            ]
            if not selected_options:
                return []
    all_users = get_participants(ParticipantType.HUMAN, True)
    options = [u.display_name for u in all_users]

    selected = st.multiselect(
        f"Users member of this Org [{len(selected_options)}]",
        options=options,
        default=selected_options,
        disabled=disabled,
    )
    return selected


def render_orgs_of_org(
    title: str, selected_org: Participant, disabled: bool
) -> list[str]:
    """Render the users of this org but don't let them change yet"""
    st.write(title)

    # get the users connected to this org
    selected_options = []
    with ParticipantRelationRepository(get_db()) as repo:
        members_of_org = repo.get_reverse(selected_org.id, ("MEMBER OF",))
        if members_of_org:
            selected_options = [
                m.participant.display_name
                for m in members_of_org
                if m.participant.participant_type == ParticipantType.ORG_UNIT
            ]
            if not selected_options:
                return []
    all_orgs = get_participants(ParticipantType.ORG_UNIT, True)
    options = [o.display_name for o in all_orgs]

    selected = st.multiselect(
        f"Orgs member of this Org [{len(selected_options)}]",
        options=options,
        default=selected_options,
        disabled=disabled,
    )
    return selected


def render_org_is_member_of(
    title: str, selected_org: Participant, disabled: bool
) -> list[str]:
    """Render the users of this org but don't let them change yet"""
    st.write(title)

    # get the users connected to this org
    selected_options = []
    with ParticipantRelationRepository(get_db()) as repo:
        all_orgs = get_participants(ParticipantType.ORG_UNIT, False)
        options = [o.display_name for o in all_orgs]
        member_of_org = repo.get(selected_org.id, ("MEMBER OF",))
        if member_of_org:
            selected_options = [
                m.participant.display_name
                for m in member_of_org
                if m.participant.participant_type == ParticipantType.ORG_UNIT
            ]

        selected = st.multiselect(
            f"Org is member of [{len(selected_options)}]",
            options=options,
            default=selected_options,
            disabled=disabled,
        )
        return selected


def save_role_changes(
    pati_repo: ParticipantRepository,
    selected_org_unit: Participant,
    selected_roles: list[str],
) -> bool:
    """Saves the changes to the database. Returns True if a change was made to the database"""
    org_roles = [r.name for r in selected_org_unit.roles if r.name != "PUBLIC"]
    new_roles, deleted_roles = compare_lists(list(selected_roles), org_roles)

    logger.debug(
        f"Org Unit: {selected_org_unit.name} - new_roles: {', '.join(new_roles)} deleted roles: {', '.join(deleted_roles)}"
    )

    if new_roles:
        add_roles(pati_repo, selected_org_unit, new_roles)
    if deleted_roles:
        delete_roles(pati_repo, selected_org_unit, deleted_roles)

    if new_roles or deleted_roles:
        return True
    return False


def render_org_units_selectbox() -> Optional[Participant]:

    show_only_active = st.toggle(label="Show only active", value=True)
    if show_only_active:
        org_units = sorted(
            [
                v["display_name"]
                for v in st.session_state.users_all_org_units.values()
                if v["state"] == "ACTIVE"
            ]
        )
    else:
        org_units = sorted(st.session_state.users_all_org_units.keys())

    key = "org_units_selectbox"
    selected_key = key + "_selected"
    if (
        selected_key in st.session_state
        and st.session_state[selected_key]
        and st.session_state[selected_key] in org_units
    ):
        index = org_units.index(st.session_state[selected_key])
    else:
        index = 0
    selected = st.selectbox(
        label="Select an Organizational Unit",
        options=org_units,
        key=key,
        index=index,
    )
    if selected:
        st.session_state[selected_key] = selected
        if selected_org_unit := get_participant(
            st.session_state.users_all_org_units[selected]["id"],
            include_relations=True,
            include_proxies=False,
        ):
            return selected_org_unit
        else:
            st.error(f"Selected org_unit not found. {selected} ")
            # Remove the user from the session_state.user_users
            st.session_state.users_all_org_units.pop(selected)
            st.stop()

    return None


def render_create_org_unit_form(title: str):
    """Renders the create user form and handles the submit button"""
    """Renders the create org unit form and handles the submit button"""
    disabled = False
    with st.form(key="create_org_unit_form", clear_on_submit=False):
        st.write(title)
        org_unit_name = st.text_input(
            "Name",
            help="Name or the organizational unit (Group, Team, Department)",
            placeholder="",
            disabled=disabled,
        )
        display_name = st.text_input(
            "Display Name", placeholder="", help="", disabled=disabled
        )
        description = st.text_input(
            "Description (Optional)",
            placeholder="",
            help="",
            disabled=disabled,
        )

        if st.form_submit_button("Create", disabled=disabled):
            if not display_name or not org_unit_name:
                st.error("Please fill in all fields")
            else:
                if not is_valid_name(org_unit_name.strip()):
                    st.error(
                        "Invalid Name. Name must be at least 2 characters long, start with a letter, can contain numbers, underscores and hyphens"
                    )
                    st.stop()

                org_unit_name = org_unit_name.upper()
                with ParticipantRepository(get_db()) as pati_repo:
                    exists: Union[bool | str] = pati_repo.exists(
                        "name", org_unit_name, ParticipantType.ORG_UNIT
                    )
                    if exists:
                        if exists == ParticipantState.TERMINATED:
                            st.error(
                                f"Org Unit {org_unit_name!a} already exists but is not active"
                            )
                        else:
                            st.error(
                                f"Org Unit {org_unit_name!a} already exists"
                            )

                        return
                    exists = pati_repo.exists(
                        "display_name", display_name, ParticipantType.ORG_UNIT
                    )
                    if exists:
                        if exists == ParticipantState.TERMINATED:
                            st.error(
                                f"Org Unit with the same display name: {display_name!a} already exists but is not active"
                            )
                        else:
                            st.error(
                                f"Org Unit with the same display name: {display_name!a} already exists"
                            )
                        return
                    try:
                        create = ParticipantCreate(
                            name=org_unit_name,
                            display_name=display_name,
                            description=description,
                            created_by=st.session_state.current_user[
                                "username"
                            ],
                            participant_type=ParticipantType.ORG_UNIT,
                        )
                        _ = pati_repo.create(create)

                        # Now add him to the session state.
                    except Exception as e:
                        logger.exception(f"Org Unit creation failed: {e}")
                        st.error("Oops that went wrong")
                        pati_repo.rollback()
                    else:
                        pati_repo.commit()
                        st.success(
                            f"Organizational unit {org_unit_name} created"
                        )
                        time.sleep(1)
                        # Clear the cache, because get_participants is cached and must be reread
                        get_participants.clear()
                        init_session_state()
                        st.rerun()  # to render the user selectbox new.


def render_org_units_update(selected_org_unit: Participant):
    enforcer = get_policy_enforcer()
    disabled = not enforcer.enforce(
        st.session_state.current_user["username"], "org_units", "write"
    )
    with st.form(key="update_org_unit_form", border=False):
        if selected_org_unit.state == ParticipantState.ACTIVE:
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
        name = st.text_input(
            label="Name",
            value=selected_org_unit.name,
            disabled=disabled,
        )
        display_name = st.text_input(
            label="Display Name",
            value=selected_org_unit.display_name,
            disabled=disabled,
        )
        description = st.text_input(
            label="Description",
            value=selected_org_unit.description,
            disabled=disabled,
        )

        _ = render_org_is_member_of(
            "",
            selected_org_unit,
            True,  # do not let them change it here disabled
        )

        selected_roles = render_roles_granted_to_org(
            "", selected_org_unit, disabled
        )

        _ = render_users_of_org(
            "",
            selected_org_unit,
            True,  # do not let them change it here disabled
        )

        _ = render_orgs_of_org(
            "",
            selected_org_unit,
            True,  # do not let them change it here disabled
        )

        if st.form_submit_button("Save", disabled=disabled):
            if len(display_name) == 0:
                st.error("Display name cannot be empty")
                st.stop()

            with ParticipantRepository(get_db()) as pati_repo:

                try:
                    role_changes = save_role_changes(
                        pati_repo, selected_org_unit, selected_roles
                    )
                except Exception as e:
                    pati_repo.rollback()
                    logger.exception(e)
                    st.exception(e)
                    raise
                else:
                    org_changes: dict[str, Any] = dict()
                    if selected_org_unit.display_name != display_name:
                        org_changes["display_name"] = display_name
                    if selected_org_unit.name != name:
                        org_changes["name"] = name
                    if selected_org_unit.description != description:
                        org_changes["description"] = description
                    if state_toggle != str(selected_org_unit.state):
                        org_changes["state"] = state_toggle
                    if org_changes:
                        org_changes["updated_by"] = (
                            st.session_state.current_user["username"]
                        )
                        update = ParticipantUpdate.model_validate(org_changes)
                        try:
                            pati_repo.update(selected_org_unit.id, update)
                        except Exception as e:
                            pati_repo.rollback()
                            logger.exception(e)
                            st.exception(e)
                            raise
                        else:
                            pati_repo.commit()
                            st.success(
                                f"Org Unit {selected_org_unit.display_name} saved"
                            )
                            time.sleep(1)
                            get_participants.clear()  # To reread the changes.
                            init_session_state()
                            st.rerun()
                    else:
                        if not role_changes:
                            st.info("No changes to save")
                        else:
                            # Only roles got changed
                            pati_repo.commit()
                            st.success(
                                f"Org Unit {selected_org_unit.display_name} saved"
                            )
                            get_participants.clear()  # To reread the changes.
                            init_session_state()
                            st.rerun()


def render_org_units():
    """Renders the Users dialog"""
    init_session_state()
    with st.container(border=True):
        st.write("## Organizational Units")
        selected_org_unit = render_org_units_selectbox()
        if selected_org_unit:
            render_org_units_update(selected_org_unit)

    enforcer = get_policy_enforcer()
    if enforcer.enforce(
        st.session_state.current_user["username"], "org_units", "create"
    ):
        st.divider()
        render_create_org_unit_form("## Create Org Unit")
