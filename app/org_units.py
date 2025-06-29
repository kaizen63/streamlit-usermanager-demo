"""Handles the Org Units page"""

import logging
import time
from typing import Any

import streamlit as st
from common import safe_index
from config import settings
from db import get_session
from participant_utilities import (
    check_pati_exists,
    get_org_units,
    get_participant_by_display_name,
    get_roles,
    get_users,
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
from user_permissions import get_policy_enforcer
from users import add_roles, delete_roles, process_participant_changes

logger = logging.getLogger(settings.LOGGER_NAME)


def render_roles_granted_to_org(
    title: str, selected_org: Participant, disabled: bool
) -> list[str]:
    """Render the roles multiselect"""
    st.write(title)
    selected_org_roles: set[str] = {
        r.name for r in selected_org.roles if r.name != "PUBLIC"
    }

    key = "org_unit_roles_multiselect"
    dis = disabled or selected_org.state == ParticipantState.TERMINATED

    roles = get_roles(only_active=True)

    options = [
        r.name for r in roles if r.name != "PUBLIC"
    ]  # remove the ones we  do not want

    selected_roles = st.multiselect(
        f"Roles granted to this Org [{len(selected_org_roles)}]",
        options=options,
        default=selected_org_roles if selected_org_roles else None,
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
    with get_session() as session, ParticipantRelationRepository(session) as repo:
        members_of_org = repo.get_reverse(selected_org.id, ("MEMBER OF",))
        if members_of_org:
            selected_options = [
                m.participant.display_name
                for m in members_of_org
                if m.participant.participant_type == ParticipantType.HUMAN
            ]
            if not selected_options:
                return []
    all_users = get_users(only_active=True)
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
    with get_session() as session, ParticipantRelationRepository(session) as repo:
        members_of_org = repo.get_reverse(selected_org.id, ("MEMBER OF",))
        if members_of_org:
            selected_options = [
                m.participant.display_name
                for m in members_of_org
                if m.participant.participant_type == ParticipantType.ORG_UNIT
            ]
            if not selected_options:
                return []
    all_orgs = get_org_units(only_active=True)
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
    with get_session() as session, ParticipantRelationRepository(session) as repo:
        all_orgs = get_org_units(only_active=False, include_relations=True)
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

    return process_participant_changes(
        pati_repo,
        selected_org_unit,
        "roles",
        org_roles,
        selected_roles,
        add_func=add_roles,
        delete_func=delete_roles,
    )


def render_org_units_selectbox() -> Participant | None:
    """Renders the Org Units selectbox. Shows the Org Units display names"""
    show_only_active = st.toggle(label="Show only active", value=True)
    all_org_units = get_org_units(only_active=show_only_active, include_relations=False)
    org_units = [o.display_name for o in all_org_units]
    key = "org_units_selectbox"
    selected_key = key + "_selected"

    index = safe_index(org_units, st.session_state.get(selected_key), 0)

    selected = st.selectbox(
        label="Select an Organizational Unit",
        options=org_units,
        key=key,
        index=index,
    )
    if selected:
        st.session_state[selected_key] = selected
        if selected_org_unit := get_participant_by_display_name(
            selected,
            ParticipantType.ORG_UNIT,
            include_relations=True,
            include_proxies=False,
        ):
            return selected_org_unit
        st.error(f"Selected org_unit not found. {selected} ")
        st.stop()

    return None


def check_org_unit_exists(
    pati_repo: ParticipantRepository, name: str, display_name: str
) -> bool:
    """
    Checks if the user exists by name or display name, whether active or terminated.

    Returns True if the user already exists, False otherwise.
    """
    return check_pati_exists(pati_repo, ParticipantType.ORG_UNIT, name, display_name)


def render_create_org_unit_form(title: str) -> None:
    """Renders the create user form and handles the submit button"""
    """Renders the create org unit form and handles the submit button"""

    # noinspection PyShadowingNames
    def process_form_submission(
        org_unit_name: str, display_name: str, description: str
    ) -> None:
        if not display_name or not org_unit_name:
            st.error("Please fill in all fields")
            return
        if not is_valid_name(org_unit_name.strip()):
            st.error(
                "Invalid name. It must be at least 2 characters long, start with a letter, "
                "and may include numbers, underscores and hyphens."
            )
            st.stop()

        org_unit_name = org_unit_name.upper()
        with get_session() as session, ParticipantRepository(session) as pati_repo:
            if check_org_unit_exists(pati_repo, org_unit_name, display_name):
                return
            try:
                create = ParticipantCreate(
                    name=org_unit_name,
                    display_name=display_name,
                    description=description,
                    created_by=st.session_state.username,
                    participant_type=ParticipantType.ORG_UNIT,
                )
                _ = pati_repo.create(create)

                # Now add him to the session state.
            except Exception as e:
                logger.exception(f"Org Unit creation failed: {e}")
                st.error("Oops that went wrong")
                pati_repo.rollback()
            else:
                finalize_org_unit_creation(pati_repo, org_unit_name)

    # noinspection PyShadowingNames
    def finalize_org_unit_creation(
        pati_repo: ParticipantRepository, org_unit_name: str
    ) -> None:
        pati_repo.commit()
        st.success(f"Organizational unit {org_unit_name} created")
        time.sleep(1)
        # Clear the cache, because get_participants is cached and must be reread
        get_org_units.clear()
        st.rerun()  # to render the user selectbox new.

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
            process_form_submission(org_unit_name, display_name, description)


def save_org_changes(
    pati_repo: ParticipantRepository,
    selected_org_unit: Participant,
    changes: dict[str, Any],
) -> None:
    """Saves the Org Unit changes"""
    changes["updated_by"] = (
        st.session_state.username if "updated_by" not in changes else None
    )

    update = ParticipantUpdate.model_validate(changes)
    try:
        pati_repo.update(selected_org_unit.id, update)
    except Exception as e:
        pati_repo.rollback()
        logger.exception(e)
        st.exception(e)
        raise
    else:
        pati_repo.commit()
        get_org_units.clear()  # To reread the changes.
        st.success(f"Org Unit {selected_org_unit.display_name} saved")


def render_update_org_unit_form(selected_org_unit: Participant) -> None:
    """Renders the update dialog"""

    def get_org_changes() -> dict[str, str | None]:
        return {
            "display_name": (
                display_name if selected_org_unit.display_name != display_name else None
            ),
            "name": (name if selected_org_unit.name != name else None),
            "description": (
                description if selected_org_unit.description != description else None
            ),
            "state": (
                state_toggle if state_toggle != str(selected_org_unit.state) else None
            ),
        }

    def process_org_changes(
        pati_repo: ParticipantRepository, roles_changed: bool
    ) -> None:
        org_changes = {k: v for k, v in get_org_changes().items() if v is not None}

        if org_changes:
            save_org_changes(pati_repo, selected_org_unit, org_changes)
            time.sleep(1)
            st.rerun()
        elif not roles_changed:
            st.info("No changes to save")
        else:
            # Only roles got changed
            pati_repo.commit()
            get_org_units.clear()
            st.success(f"Org Unit {selected_org_unit.display_name} saved")
            st.rerun()

    def process_form_submission() -> None:
        if len(display_name) == 0:
            st.error("Display name cannot be empty")
            st.stop()

        with get_session() as session, ParticipantRepository(session) as pati_repo:
            try:
                roles_changed = save_role_changes(
                    pati_repo, selected_org_unit, selected_roles
                )
            except Exception as e:
                pati_repo.rollback()
                logger.exception(e)
                st.exception(e)
                raise
            else:
                process_org_changes(pati_repo, roles_changed)

    enforcer = get_policy_enforcer()
    disabled = not enforcer.enforce(st.session_state.username, "org_units", "write")
    with st.form(key="update_org_unit_form", border=False):
        index = 0 if selected_org_unit.state == ParticipantState.ACTIVE else 1
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

        render_org_is_member_of(
            "",
            selected_org_unit,
            True,
        )  # do not let them change it here disabled
        selected_roles = render_roles_granted_to_org("", selected_org_unit, disabled)
        render_users_of_org(
            "",
            selected_org_unit,
            True,
        )  # do not let them change it here disabled
        render_orgs_of_org(
            "",
            selected_org_unit,
            True,
        )  # do not let them change it here disabled

        if st.form_submit_button("Save", disabled=disabled):
            process_form_submission()


def render_org_units() -> None:
    """Renders the Users dialog"""
    with st.container(border=True):
        st.write("## Organizational Units")
        selected_org_unit = render_org_units_selectbox()
        if selected_org_unit:
            render_update_org_unit_form(selected_org_unit)

    enforcer = get_policy_enforcer()
    if enforcer.enforce(st.session_state.username, "org_units", "create"):
        st.divider()
        render_create_org_unit_form("## Create Org Unit")
