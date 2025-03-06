"""Handles User Creation/Update"""

import logging
import time
from typing import Any, Callable, Literal, Optional, TypeAlias

import streamlit as st
from common import (
    APP_ROLES,
    AppRoles,
    compare_lists,
    get_policy_enforcer,
    is_administrator,
    safe_index,
)
from config import settings
from db import get_db
from participant_utilities import (
    check_pati_exists,
    get_org_units,
    get_participant_by_display_name,
    get_participant_ids,
    get_users,
)
from participants import (
    Participant,
    ParticipantCreate,
    ParticipantRelationType,
    ParticipantRepository,
    ParticipantState,
    ParticipantType,
    ParticipantUpdate,
)
from validate_email import validate_email

logger = logging.getLogger(settings.LOGGER_NAME)


def render_roles(
    title: str, selected_user: Participant, disabled: bool
) -> list[str]:
    """Render the roles multiselect"""
    st.write(title)
    users_roles: Optional[set[str]] = set(
        [r.name for r in selected_user.roles if r.name != "PUBLIC"]
    )
    # Only administrator can assign another one the administrator roles
    options = sorted(
        [
            r
            for r in APP_ROLES
            if r != "ADMINISTRATOR"
            or "ADMINISTRATOR"
            in st.session_state.current_user["effective_roles"]
        ]
    )
    key = "users_roles_multiselect"
    dis = disabled or (
        True if (selected_user.state == ParticipantState.TERMINATED) else False
    )
    # remove items from the defaults which are not in the options. Otherwise -> crash
    if users_roles:
        defaults = [item for item in options if item in list(users_roles)]
    else:
        defaults = None

    selected_roles = st.multiselect(
        "Roles",
        options=options,
        default=defaults,
        key=key,
        disabled=dis,
    )
    return selected_roles


def render_effective_roles(title: str, selected_user: Participant) -> None:
    """Render the roles multiselect"""
    st.write(title)
    with ParticipantRepository(get_db()) as repo:
        effective_roles = list(repo.compute_effective_roles(selected_user))

    options = [x for x in effective_roles if x != "PUBLIC"]
    # user can only see, but not do anything with the effective roles
    _ = st.multiselect(
        "Effective Roles",
        options=options,
        default=options,
        disabled=True,
        label_visibility="collapsed",
    )
    return None


def render_org_units(
    title: str, selected_user: Participant, disabled: bool
) -> list[str]:
    """Renders the Org Units page and returns a list of org unit display names"""
    st.write(title)
    selected_user_orgs: Optional[set[str]] = set(
        [ou.display_name for ou in selected_user.org_units]
    )
    if not selected_user_orgs:
        selected_user_orgs = None
    all_orgs = get_org_units(only_active=True)
    options = [o.display_name for o in all_orgs]

    dis = disabled or (
        True if (selected_user.state == ParticipantState.TERMINATED) else False
    )

    key = "users_member_of_multiselect"
    member_of = st.multiselect(
        "Member of",
        options=options,
        default=selected_user_orgs,
        key=key,
        disabled=dis,
    )
    return member_of


def render_proxy_of(
    title: str, selected_user: Participant, disabled: bool
) -> list[str]:
    """Renders the Proxy of section"""
    st.write(title)
    selected_users_proxy_of: Optional[set[str]] = set(
        [po.display_name for po in selected_user.proxy_of]
    )
    if not selected_users_proxy_of:
        selected_users_proxy_of = None
    all_users: list[Participant] = get_users(only_active=False)
    options = sorted(
        [
            x.display_name
            for x in all_users
            if x.display_name != st.session_state.get("users_selectbox", "")
        ]
    )
    dis = disabled or (
        True if (selected_user.state == ParticipantState.TERMINATED) else False
    )

    key = "users_proxy_of_multiselect"
    proxy_of = st.multiselect(
        "Select users or leave empty",
        options=options,
        default=selected_users_proxy_of,
        key=key,
        placeholder="Choose a user or leave empty",
        disabled=dis,
    )
    return proxy_of


def render_proxies(
    title: str, selected_user: Participant, disabled: bool
) -> list[str]:
    """Render the proxies"""
    st.write(title)
    selected_users_proxies: Optional[set[str]] = set(
        [po.display_name for po in selected_user.proxies]
    )
    if not selected_users_proxies:
        selected_users_proxies = None
    all_users = [
        x.display_name
        for x in get_users(only_active=True)
        if x.id != selected_user.id
    ]
    dis = disabled or (
        True if (selected_user.state == ParticipantState.TERMINATED) else False
    )

    key = "users_proxies_multiselect"
    proxies = st.multiselect(
        "Select users or leave empty",
        options=all_users,
        default=selected_users_proxies,
        key=key,
        placeholder="Choose users or leave empty",
        disabled=dis,
    )
    return proxies


def add_relations(
    pati_repo: ParticipantRepository,
    participant: Participant,
    related_participant_ids: list[int],
    relation_type: ParticipantRelationType,
) -> None:
    """Adds relations to a participant
    Args:
        pati_repo: The repository
        participant: The participant where the relation is added to
        related_participant_ids: The participant ids to connect the participant with.
        relation_type: One of GRANT, MEMBER OF or PROXY OF
    """

    if not related_participant_ids:
        return
    try:
        for r_id in related_participant_ids:
            pati_repo.add_relation(
                participant,
                r_id,
                relation_type,
                created_by=st.session_state.username,
            )
    except Exception as e:
        st.exception(e)
        logger.exception(e)
        raise e
    else:
        logger.debug(
            f"Added {relation_type.value} to {participant.name} {', '.join([str(i) for i in related_participant_ids])}"
        )


def add_reverse_relations(
    pati_repo: ParticipantRepository,
    participant: Participant,
    related_participant_ids: list[int],
    relation_type: ParticipantRelationType,
) -> None:
    """Adds reverse relations to a participant
    Args:
        pati_repo: The repository
        participant: The participant where the relation is added to
        related_participant_ids: The participant ids to connect the participant with.
        relation_type: One of GRANT, MEMBER OF or PROXY OF
    """

    if not related_participant_ids:
        return
    try:
        for r_id in related_participant_ids:
            pati_repo.add_reverse_relation(
                participant,
                r_id,
                relation_type,
                created_by=st.session_state.username,
            )
    except Exception as e:
        st.exception(e)
        logger.exception(e)
        raise e
    else:
        logger.debug(
            f"Added {relation_type=} to {participant.name} {', '.join([str(i) for i in related_participant_ids])}"
        )


def delete_relations(
    pati_repo: ParticipantRepository,
    participant: Participant,
    related_participant_ids: list[int],
    relation_type: ParticipantRelationType,
) -> None:
    """Adds relations to a participant
    Args:
        pati_repo: The repository
        participant: The participant where the relation is added to
        related_participant_ids: The participant ids to connect the participant with.
        relation_type: One of GRANT, MEMBER OF or PROXY OF
    """

    if not related_participant_ids:
        return
    try:
        for r_id in related_participant_ids:
            pati_repo.delete_relation(
                participant,
                r_id,
                relation_type,
            )
    except Exception as e:
        st.exception(e)
        logger.exception(e)
        raise e
    else:
        logger.debug(
            f"Deleted {relation_type=} to {participant.name} {', '.join([str(i) for i in related_participant_ids])}"
        )


def delete_reverse_relations(
    pati_repo: ParticipantRepository,
    participant: Participant,
    related_participant_ids: list[int],
    relation_type: ParticipantRelationType,
) -> None:
    """Deletes relations to a participant
    Args:
        pati_repo: The repository
        participant: The participant where the relation is added to
        related_participant_ids: The participant ids to connect the participant with.
        relation_type: One of GRANT, MEMBER OF or PROXY OF
    """

    if not related_participant_ids:
        return
    try:
        for r_id in related_participant_ids:
            pati_repo.delete_reverse_relation(
                participant,
                r_id,
                relation_type,
            )
    except Exception as e:
        st.exception(e)
        logger.exception(e)
        raise e
    else:
        logger.debug(
            f"Deleted {relation_type=} to {participant.name} {', '.join([str(i) for i in related_participant_ids])}"
        )


def add_roles(
    pati_repo: ParticipantRepository,
    participant: Participant,
    roles: list[str],
) -> None:
    """Adds the roles to the participant"""
    if not roles:
        return
    try:
        role_ids = get_participant_ids(ParticipantType.ROLE, "name", roles)
        add_relations(
            pati_repo,
            participant,
            role_ids,
            ParticipantRelationType.GRANT,
        )
    except Exception as e:
        st.exception(e)
        logger.exception(e)
        raise e
    else:
        logger.debug(f"Role(s): {', '.join(roles)} added")


def delete_roles(
    pati_repo: ParticipantRepository,
    participant: Participant,
    roles: list[str],
) -> None:
    """Deletes the roles to the participant"""
    if not roles:
        return

    role_ids = get_participant_ids(ParticipantType.ROLE, "name", roles)
    try:
        delete_relations(
            pati_repo,
            participant,
            role_ids,
            ParticipantRelationType.GRANT,
        )
    except Exception as e:
        st.exception(e)
        raise
    else:
        logger.debug(f"Role(s): {', '.join(roles)} deleted")


def add_orgs(
    pati_repo: ParticipantRepository,
    participant: Participant,
    org_units: list[str],
) -> None:
    """Adds the org_units to the participant"""
    if not org_units:
        return
    try:
        org_ids = get_participant_ids(
            ParticipantType.ORG_UNIT, "display_name", org_units
        )

        add_relations(
            pati_repo,
            participant,
            org_ids,
            ParticipantRelationType.MEMBER_OF,
        )
    except Exception as e:
        st.exception(e)
        logger.exception(e)
        raise
    else:
        logger.debug(f"User added to these Org Units: {', '.join(org_units)}")


def add_proxy_of(
    pati_repo: ParticipantRepository,
    participant: Participant,
    proxy_of: list[str],
) -> None:
    """Adds the proxy_of to the participant"""
    if not proxy_of:
        return
    try:
        user_ids = get_participant_ids(
            ParticipantType.HUMAN, "display_name", proxy_of
        )

        add_relations(
            pati_repo,
            participant,
            user_ids,
            ParticipantRelationType.PROXY_OF,
        )
    except Exception as e:
        st.exception(e)
        logger.exception(e)
        raise e
    else:
        logger.debug(f"User is now new proxy of: {', '.join(proxy_of)}")


def delete_proxy_of(
    pati_repo: ParticipantRepository,
    participant: Participant,
    proxy_of: list[str],
) -> None:
    """Deletes the proxy_of to the participant"""
    if not proxy_of:
        return
    try:
        user_ids = get_participant_ids(
            ParticipantType.HUMAN, "display_name", proxy_of
        )
        delete_relations(
            pati_repo,
            participant,
            user_ids,
            ParticipantRelationType.PROXY_OF,
        )
    except Exception as e:
        st.exception(e)
        logger.exception(e)
    else:
        logger.debug(f"User is not anymore a proxy of: {', '.join(proxy_of)}")


def delete_orgs(
    pati_repo: ParticipantRepository,
    participant: Participant,
    org_units: list[str],
) -> None:
    """Adds the roles to the participant"""
    if not org_units:
        return
    try:
        org_ids = get_participant_ids(
            ParticipantType.ORG_UNIT, "display_name", org_units
        )
        delete_relations(
            pati_repo,
            participant,
            org_ids,
            ParticipantRelationType.MEMBER_OF,
        )
    except Exception as e:
        st.exception(e)
        logger.exception(e)
        raise e
    else:
        logger.debug(
            f"User removed from these Org Units: {', '.join(org_units)}"
        )


def add_proxy(
    pati_repo: ParticipantRepository,
    participant: Participant,
    proxies: list[str],
) -> None:
    """Adds a proxy to a participant"""
    if not proxies:
        return
    try:
        user_ids = get_participant_ids(
            ParticipantType.HUMAN, "display_name", proxies
        )
        add_reverse_relations(
            pati_repo,
            participant,
            user_ids,
            ParticipantRelationType.PROXY_OF,
        )
    except Exception as e:
        st.exception(e)
        logger.exception(e)
        raise e
    else:
        logger.debug(f"New proxies: {', '.join(proxies)}")


def delete_proxy(
    pati_repo: ParticipantRepository,
    participant: Participant,
    proxies: list[str],
) -> None:
    """Deletes the proxy from a participant"""
    if not proxies:
        return
    try:
        user_ids = get_participant_ids(
            ParticipantType.HUMAN, "display_name", proxies
        )
        delete_reverse_relations(
            pati_repo,
            participant,
            user_ids,
            ParticipantRelationType.PROXY_OF,
        )
    except Exception as e:
        st.exception(e)
        logger.exception(e)
        raise
    else:
        logger.debug(f"Deleted proxies: {', '.join(proxies)}")


EntityNameType: TypeAlias = Literal["roles", "org_units", "proxy_of", "proxy"]


def process_participant_changes(
    pati_repo: ParticipantRepository,
    selected_participant: Participant,
    entity_name: EntityNameType,
    current_items: list[str],
    selected_items: list[str],
    add_func: Callable[[ParticipantRepository, Participant, list[str]], None],
    delete_func: Callable[
        [ParticipantRepository, Participant, list[str]], None
    ],
) -> bool:
    """Processes the add and delete of an entity"""

    def log_changes() -> None:
        """Log what has been added and deleted from a user"""
        logger.debug(
            f"User: {selected_participant.name} - new {entity_name}: {', '.join(new_items)} "
            f"deleted {entity_name}: {', '.join(deleted_items)}"
        )

    new_items, deleted_items = compare_lists(selected_items, current_items)
    if not new_items and not deleted_items:
        return False
    log_changes()
    if new_items:
        add_func(pati_repo, selected_participant, new_items)
    if deleted_items:
        delete_func(pati_repo, selected_participant, deleted_items)
    return True if new_items or deleted_items else False


def save_user_changes(
    pati_repo: ParticipantRepository,
    selected_user: Participant,
    user_changes: dict[
        str, Any
    ],  # dict with changed columns (display name or description
    selected_roles: list[str],
    selected_org_units: list[str],
    selected_proxy_of: list[str],
    selected_proxies: list[str],
) -> bool:
    """Saves the changes to the database. Returns True if a change was made to the database"""
    changed_something = False
    logger.info(
        f"Saving user: {selected_user.name}: {selected_user.display_name}"
    )
    if user_changes:
        user_changes["updated_by"] = st.session_state.username
        update = ParticipantUpdate.model_validate(user_changes)
        try:
            pati_repo.update(selected_user.id, update)
            if update.state and update.state == ParticipantState.TERMINATED:
                pati_repo.delete_all_participant_relations(selected_user.id)
        except Exception as e:
            logger.exception(e)
            st.exception(e)
            raise
        else:
            changed_something = True

    current_roles = [r.name for r in selected_user.roles if r.name != "PUBLIC"]
    changed_something = (
        True
        if process_participant_changes(
            pati_repo,
            selected_user,
            "roles",
            current_items=current_roles,
            selected_items=selected_roles,
            add_func=add_roles,
            delete_func=delete_roles,
        )
        else changed_something
    )

    current_org_units = [ou.display_name for ou in selected_user.org_units]
    changed_something = (
        True
        if process_participant_changes(
            pati_repo,
            selected_user,
            "org_units",
            current_items=current_org_units,
            selected_items=selected_org_units,
            add_func=add_orgs,
            delete_func=delete_orgs,
        )
        else changed_something
    )

    current_proxy_of = [po.display_name for po in selected_user.proxy_of]
    changed_something = (
        True
        if process_participant_changes(
            pati_repo,
            selected_user,
            "proxy_of",
            current_items=current_proxy_of,
            selected_items=selected_proxy_of,
            add_func=add_proxy_of,
            delete_func=delete_proxy_of,
        )
        else changed_something
    )

    current_proxies = [p.display_name for p in selected_user.proxies]
    changed_something = (
        True
        if process_participant_changes(
            pati_repo,
            selected_user,
            "proxy",
            current_items=current_proxies,
            selected_items=selected_proxies,
            add_func=add_proxy,
            delete_func=delete_proxy,
        )
        else changed_something
    )

    return changed_something


def save_new_user(
    pati_repo: ParticipantRepository,
    *,
    username: str,
    display_name: str,
    description: str,
    email: str,
) -> None:
    """Saves the new user and grants the role PUBLIC to the user"""

    try:
        create = ParticipantCreate(
            name=username,
            display_name=display_name,
            created_by=st.session_state.username,
            participant_type=ParticipantType.HUMAN,
            description=description,
            email=email,
        )
        new_pati = pati_repo.create(create)

    except Exception as e:
        logger.exception(f"User creation failed: {e}")
        st.error("Oops that went wrong")
        raise
    else:
        try:
            add_roles(pati_repo, new_pati, ["PUBLIC"])
        except Exception as e:
            logger.exception(f"User assigning to role PUBLIC failed: {e}")
            raise
        else:
            return


def check_user_exists(
    pati_repo: ParticipantRepository, name: str, display_name: str
) -> bool:
    """Checks if the user exists by name or display name, whether active or terminated.
    Returns True if the user already exists, False otherwise."""
    return check_pati_exists(
        pati_repo, ParticipantType.HUMAN, name, display_name
    )


def render_create_user_form(title: str) -> None:
    """Renders the create user form and handles the submit button"""

    # noinspection PyShadowingNames
    def process_form_submission(
        username: str, display_name: str, email: str, description: str
    ) -> None:
        if not validate_email(email):
            st.error(f"Invalid Email: {email!a}")
            return

        username = username.upper()
        with ParticipantRepository(get_db()) as pati_repo:
            if check_user_exists(pati_repo, username, display_name):
                return

            try:
                save_new_user(
                    pati_repo=pati_repo,
                    username=username,
                    display_name=display_name,
                    description=description,
                    email=email,
                )
            except Exception as e:
                logger.exception(f"User creation failed: {e}")
                st.error("Oops that went wrong")
                pati_repo.rollback()
            else:
                pati_repo.commit()
                st.success(f"User {username} created")
                finalize_user_creation(display_name)

    # noinspection PyShadowingNames
    def finalize_user_creation(display_name: str):
        time.sleep(1)
        get_users.clear()
        st.session_state["users_selectbox_selected"] = display_name
        st.rerun()

    with st.form(key="create_user_form", clear_on_submit=False):
        st.write(title)
        username = st.text_input(
            "Enterprise USERID",
            help="Must be an NIQ Enterprise ID, otherwise the user cannot be authenticated",
            placeholder="DOEJOHN01",
        )
        display_name = st.text_input(
            "Display Name", placeholder="Doe, John", help="Last, First"
        )
        email = st.text_input("Email", placeholder="john.doe@nielseniq.com")
        description = st.text_input(label="Description (Optional)", value="")

        if st.form_submit_button("Create"):
            if not display_name or not username or not email:
                st.error("Please fill in all fields")
            else:
                process_form_submission(
                    username, display_name, email, description
                )


def render_user_selectbox() -> Optional[Participant]:
    """Renders the users selectbox"""
    show_only_active = st.toggle(label="Show only active", value=True)
    # for speed, we do not query the relations. This will be done when we have selected one user
    usernames = sorted(
        [
            u.display_name
            for u in get_users(
                only_active=show_only_active, include_relations=False
            )
        ]
    )
    key = "users_selectbox"
    selected_key = key + "_selected"

    index = safe_index(usernames, st.session_state.get(selected_key), 0)

    selected = st.selectbox(
        label="Select a user",
        options=usernames,
        key=key,
        index=index,
    )
    if selected:
        st.session_state[selected_key] = selected
        if selected_user := get_participant_by_display_name(
            selected,
            ParticipantType.HUMAN,
            include_relations=True,
            include_proxies=True,
        ):
            return selected_user
        else:
            st.error(f"Selected user not found. {selected} ")
            # Remove the user from the session_state.user_users
            st.session_state.users_all_users.pop(selected)
            st.stop()
    else:
        selected_user = None
    return selected_user


def render_update_user_form(selected_user: Participant) -> None:
    """Renders the roles, groups and proxies and handles the save button"""

    def get_user_changes() -> dict[str, str | None]:
        return {
            "description": (
                description
                if selected_user.description != description
                else None
            ),
            "display_name": (
                display_name
                if selected_user.display_name != display_name
                else None
            ),
            "state": (
                state_toggle
                if state_toggle != str(selected_user.state)
                else None
            ),
            "email": email if selected_user.email != email else None,
        }

    # noinspection PyShadowingNames
    def process_form_submission(pati_repo: ParticipantRepository):
        user_changes = {
            k: v for k, v in get_user_changes().items() if v is not None
        }
        try:
            updated: bool = save_user_changes(
                pati_repo,
                selected_user,
                user_changes,
                selected_roles,
                selected_org_units,
                selected_proxy_of,
                selected_proxies,
            )
        except Exception as e:
            logger.exception(e)
            pati_repo.rollback()
        else:
            handle_update_result(updated, pati_repo)

    # noinspection PyShadowingNames
    def handle_update_result(updated: bool, pati_repo: ParticipantRepository):
        if updated:
            pati_repo.commit()
            get_users.clear()
            st.success(f"User {selected_user.display_name!a} updated")
            time.sleep(1)
            st.rerun()
        else:
            st.info("No changes to save")
            time.sleep(1)

    enforcer = get_policy_enforcer()
    disabled = not enforcer.enforce(
        st.session_state.username, "users", "write"
    )

    index = 0 if selected_user.state == ParticipantState.ACTIVE else 1

    state_toggle = st.radio(
        label="Status",
        options=["ACTIVE", "TERMINATED"],
        #  captions=["Active", "Disabled"],
        horizontal=True,
        index=index,
        disabled=disabled,
    )
    st.text_input(
        label="Account Name", value=selected_user.name, disabled=True
    )
    display_name = st.text_input(
        label="Display Name",
        value=selected_user.display_name,
        disabled=disabled,
    )

    email = st.text_input(
        label="Email",
        value=selected_user.email,
        disabled=disabled,
    )

    description = st.text_input(
        label="Description", value=selected_user.description, disabled=disabled
    )

    with st.form(key="update_user_form", clear_on_submit=False):
        columns = st.columns(3)
        with columns[0]:
            selected_roles = render_roles(
                "### Roles", selected_user, disabled=disabled
            )
        with columns[1]:
            selected_org_units = render_org_units(
                "### Member of", selected_user, disabled=disabled
            )
        with columns[2]:
            selected_proxy_of = render_proxy_of(
                "### This user is Proxy of", selected_user, disabled=disabled
            )
            selected_proxies = render_proxies(
                "### Proxies of this user are:",
                selected_user,
                disabled=disabled,
            )

        render_effective_roles("Effective Roles:", selected_user)

        if st.form_submit_button("Save", disabled=disabled):
            with ParticipantRepository(get_db()) as pati_repo:
                process_form_submission(pati_repo)


def render_users() -> None:
    """Renders the Users dialog"""
    with st.container(border=True):
        st.write("## Users")
        selected_user = render_user_selectbox()
        if not selected_user:
            st.stop()

        render_update_user_form(selected_user)
    enforcer = get_policy_enforcer()
    if enforcer.enforce(st.session_state.username, "users", "create"):
        st.divider()
        render_create_user_form("## Create User")


def render_self_registration_form(title: str) -> None:
    """Self-service for managers to create themselves as users"""

    # noinspection PyShadowingNames
    def process_registration(
        username: str,
        display_name: str,
        email: str,
        job_title: str,
        login_user: dict[str, str],
    ) -> None:
        if not validate_email(email):
            st.error(f"Invalid Email: {email!a}")
            return

        username = username.upper()
        if username != login_user["username"] and not is_administrator(
            login_user["username"]
        ):
            st.error("You cannot create an account for someone else")
            st.stop()

        create = ParticipantCreate(
            name=username,
            display_name=display_name,
            email=email,
            participant_type=ParticipantType.HUMAN,
            created_by=username,
            description=job_title,
        )

        with ParticipantRepository(get_db()) as pati_repo:
            try:
                new_pati = pati_repo.create(create)
                add_roles(pati_repo, new_pati, [AppRoles.USER_READ])
            except Exception as e:
                logger.exception(e)
                st.exception(e)
                raise
            else:
                finalize_registration(pati_repo, username)

    # noinspection PyShadowingNames
    def finalize_registration(
        pati_repo: ParticipantRepository, username: str
    ) -> None:
        enforcer = get_policy_enforcer()
        enforcer.add_role_for_user(username, AppRoles.USER_READ)
        pati_repo.commit()
        st.balloons()
        st.success(
            f"User {username} was successfully created. Please logout and login again!"
        )
        st.session_state["must_register"] = False

    st.write(title)
    st.write(":red[Please register yourself below]")

    login_user = st.session_state.get("login_user")
    if not login_user:
        st.error("Oops! Something went wrong")
        st.stop()

    with st.form(key="register_manager_form", clear_on_submit=False):
        username = st.text_input("EnterpriseID", value=login_user["username"])
        display_name = st.text_input(
            "Display Name", value=login_user["display_name"]
        )
        email = st.text_input("Email", value=login_user["email"])
        job_title = st.text_input("Job Title", value=login_user["title"])

        st.divider()
        conditions_accepted = st.checkbox(
            "Accept terms and conditions",
            value=False,
            key="users_user_terms_accepted_checkbox",
        )

        if st.form_submit_button("Register"):
            if conditions_accepted:
                process_registration(
                    username, display_name, email, job_title, login_user
                )
            else:
                st.error("Please accept terms and conditions")
                st.stop()
