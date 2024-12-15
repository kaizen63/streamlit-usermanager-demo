import logging
import time
from typing import Any, Optional, Union

import streamlit as st
from common import (
    APP_ROLES,
    AppRoles,
    MissingStateVariableError,
    compare_lists,
    get_participant,
    get_participants,
    get_policy_enforcer,
    is_administrator,
    set_org_units_into_session_state,
    set_roles_into_session_state,
    set_users_into_session_state,
    get_st_current_user,
)
from config import settings
from participants import (
    Participant,
    ParticipantCreate,
    ParticipantRelationType,
    ParticipantRepository,
    ParticipantState,
    ParticipantType,
    ParticipantUpdate,
)
from db import get_db
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
    st.write(title)
    selected_user_orgs: Optional[set[str]] = set(
        [ou.display_name for ou in selected_user.org_units]
    )
    if not selected_user_orgs:
        selected_user_orgs = None
    all_orgs = st.session_state.users_all_org_units.keys()

    dis = disabled or (
        True if (selected_user.state == ParticipantState.TERMINATED) else False
    )

    key = "users_member_of_multiselect"
    member_of = st.multiselect(
        "Member of",
        options=all_orgs,
        default=selected_user_orgs,
        key=key,
        disabled=dis,
    )
    return member_of


def render_proxy_of(
    title: str, selected_user: Participant, disabled: bool
) -> list[str]:
    st.write(title)
    selected_users_proxy_of: Optional[set[str]] = set(
        [po.display_name for po in selected_user.proxy_of]
    )
    if not selected_users_proxy_of:
        selected_users_proxy_of = None
    all_users = [
        x
        for x in st.session_state.users_all_users.keys()
        if x != st.session_state.get("users_selectbox", "")
    ]
    dis = disabled or (
        True if (selected_user.state == ParticipantState.TERMINATED) else False
    )

    key = "users_proxy_of_multiselect"
    proxy_of = st.multiselect(
        "Select users or leave empty",
        options=all_users,
        default=selected_users_proxy_of,
        key=key,
        placeholder="Choose a user or leave empty",
        disabled=dis,
    )
    return proxy_of


def render_proxies(
    title: str, selected_user: Participant, disabled: bool
) -> list[str]:
    st.write(title)
    selected_users_proxies: Optional[set[str]] = set(
        [po.display_name for po in selected_user.proxies]
    )
    if not selected_users_proxies:
        selected_users_proxies = None
    all_users = [
        x
        for x in st.session_state.users_all_users.keys()
        if x != st.session_state.get("users_selectbox", "")
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
                created_by=st.session_state.current_user["username"],
            )
    except Exception as e:
        st.exception(e)
        logger.exception(e)
        raise e
    else:
        logger.debug(
            f"Added {relation_type=} to {participant.name} {', '.join([str(i) for i in related_participant_ids])}"
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
                created_by=st.session_state.current_user["username"],
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
        if "users_all_roles" not in st.session_state:
            logger.fatal("Missing state variable 'users_all_roles'")
            raise MissingStateVariableError("users_all_roles")

        related_roles_ids = [
            st.session_state.users_all_roles[role]["id"] for role in roles
        ]
        add_relations(
            pati_repo,
            participant,
            related_roles_ids,
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
    if "users_all_roles" not in st.session_state:
        logger.fatal("Missing state variable 'users_all_roles'")
        raise MissingStateVariableError("users_all_roles")

    related_roles_ids = [
        st.session_state.users_all_roles[role]["id"] for role in roles
    ]
    try:
        delete_relations(
            pati_repo,
            participant,
            related_roles_ids,
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
        if "users_all_org_units" not in st.session_state:
            logger.fatal("Missing state variable 'users_all_org_units'")
            raise MissingStateVariableError("users_all_org_units")

        related_org_ids = [
            st.session_state.users_all_org_units[org_unit]["id"]
            for org_unit in org_units
        ]
        add_relations(
            pati_repo,
            participant,
            related_org_ids,
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
        if "users_all_users" not in st.session_state:
            logger.fatal("Missing state variable 'users_all_users'")
            raise MissingStateVariableError("users_all_users")

        related_user_ids = [
            st.session_state.users_all_users[po]["id"] for po in proxy_of
        ]
        add_relations(
            pati_repo,
            participant,
            related_user_ids,
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
    """Delets the proxy_of to the participant"""
    if not proxy_of:
        return
    try:
        if "users_all_users" not in st.session_state:
            logger.fatal("Missing state variable 'users_all_users'")
            raise MissingStateVariableError("users_all_users")

        related_user_ids = [
            st.session_state.users_all_users[po]["id"] for po in proxy_of
        ]
        delete_relations(
            pati_repo,
            participant,
            related_user_ids,
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
        if "users_all_org_units" not in st.session_state:
            logger.fatal("Missing state variable 'users_all_org_units'")
            raise MissingStateVariableError("users_all_org_units")

        related_org_ids = [
            st.session_state.users_all_org_units[org_unit]["id"]
            for org_unit in org_units
        ]
        delete_relations(
            pati_repo,
            participant,
            related_org_ids,
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
        if "users_all_users" not in st.session_state:
            logger.fatal("Missing state variable 'users_all_users'")
            raise MissingStateVariableError("users_all_users")

        user_ids = [
            st.session_state.users_all_users[pr]["id"] for pr in proxies
        ]
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
        if "users_all_users" not in st.session_state:
            logger.fatal("Missing state variable 'users_all_users'")
            raise MissingStateVariableError("users_all_users")

        user_ids = [
            st.session_state.users_all_users[pr]["id"] for pr in proxies
        ]
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
    logger.info(
        f"Saving user: {selected_user.name}: {selected_user.display_name}"
    )
    if user_changes:
        user_changes["updated_by"] = st.session_state.current_user["username"]
        update = ParticipantUpdate.model_validate(user_changes)
        try:
            pati_repo.update(selected_user.id, update)
            if update.state and update.state == ParticipantState.TERMINATED:
                pati_repo.delete_all_participant_relations(selected_user.id)
        except Exception as e:
            logger.exception(e)
            st.exception(e)
            raise

    user_roles = [r.name for r in selected_user.roles if r.name != "PUBLIC"]
    new_roles, deleted_roles = compare_lists(list(selected_roles), user_roles)

    logger.debug(
        f"User: {selected_user.name} - new_roles: {', '.join(new_roles)} deleted roles: {', '.join(deleted_roles)}"
    )

    user_org_units = [r.display_name for r in selected_user.org_units]
    new_org_units, deleted_org_units = compare_lists(
        selected_org_units, user_org_units
    )
    logger.debug(
        f"User: {selected_user.name} - new_org_units: {', '.join(new_org_units)} deleted org_units: "
        + f"{', '.join(deleted_org_units)}"
    )

    user_proxy_of = [r.display_name for r in selected_user.proxy_of]
    new_proxy_of, deleted_proxy_of = compare_lists(
        selected_proxy_of, user_proxy_of
    )
    logger.debug(
        f"User: {selected_user.name} - new_proxy_of: {', '.join(new_proxy_of)} deleted proxy_of: {', '.join(deleted_proxy_of)}"
    )

    user_proxies = [r.display_name for r in selected_user.proxies]
    new_proxies, deleted_proxies = compare_lists(
        selected_proxies, user_proxies
    )
    logger.debug(
        f"User: {selected_user.name} - new_proxies: {', '.join(new_proxies)} deleted proxies: {', '.join(deleted_proxies)}"
    )

    if new_roles:
        add_roles(pati_repo, selected_user, new_roles)
    if deleted_roles:
        delete_roles(pati_repo, selected_user, deleted_roles)
    if new_org_units:
        add_orgs(pati_repo, selected_user, new_org_units)
    if deleted_org_units:
        delete_orgs(pati_repo, selected_user, deleted_org_units)
    if new_proxy_of:
        add_proxy_of(pati_repo, selected_user, new_proxy_of)
    if deleted_proxy_of:
        delete_proxy_of(pati_repo, selected_user, deleted_proxy_of)
    if new_proxies:
        add_proxy(pati_repo, selected_user, new_proxies)
    if deleted_proxies:
        delete_proxy(pati_repo, selected_user, deleted_proxies)

    if (
        new_roles
        or deleted_roles
        or new_org_units
        or deleted_org_units
        or new_proxy_of
        or deleted_proxy_of
        or new_proxies
        or deleted_proxies
        or user_changes
    ):
        return True
    return False


def render_create_user_form(title: str):
    """Renders the create user form and handles the submit button"""
    with st.form(key="create_user_form", clear_on_submit=False):
        st.write(title)
        username = st.text_input(
            "USERID",
            help="Must be a valid userid, otherwise the user cannot be authenticated",
            placeholder="DOEJOHN01",
        )
        display_name = st.text_input(
            "Display Name", placeholder="Doe, John", help="Last, First"
        )

        email = st.text_input("Email", placeholder="john.doe@acme.com")
        description = st.text_input(label="Description (Optional)", value="")

        if st.form_submit_button("Create"):
            if not display_name or not username or not email:
                st.error("Please fill in all fields")
            else:
                # Now check if the user already exists. Can also be a terminated one
                if not validate_email(email):
                    st.error(f"Invalid Email: {email!a}")
                    return

                username = username.upper()
                with ParticipantRepository(get_db()) as pati_repo:
                    exists: Union[bool | str] = pati_repo.exists(
                        "name", username, ParticipantType.HUMAN
                    )
                    if exists:
                        if exists == ParticipantState.TERMINATED:
                            st.error(
                                f"Username: {username!a} already exists but is not active"
                            )
                        else:
                            st.error(f"Username: {username!a} already exists")

                        return
                    exists = pati_repo.exists(
                        "display_name", display_name, ParticipantType.HUMAN
                    )
                    if exists:
                        if exists == ParticipantState.TERMINATED:
                            st.error(
                                f"User with the same name: {display_name!a} already exists but is not active"
                            )
                        else:
                            st.error(
                                f"User with the same name: {display_name!a} already exists"
                            )
                        return
                    try:
                        create = ParticipantCreate(
                            name=username,
                            display_name=display_name,
                            created_by=st.session_state.current_user[
                                "username"
                            ],
                            participant_type=ParticipantType.HUMAN,
                            description=description,
                            email=email,
                        )
                        new_pati = pati_repo.create(create)

                        # Now add him to the session state.
                    except Exception as e:
                        logger.exception(f"User creation failed: {e}")
                        st.error("Oops that went wrong")
                        pati_repo.rollback()
                    else:
                        try:
                            add_roles(pati_repo, new_pati, ["PUBLIC"])
                        except Exception as e:
                            logger.exception(
                                f"User assigning to role PUBLIC failed: {e}"
                            )
                        else:
                            pati_repo.commit()
                            st.success(f"User {username} created")
                            time.sleep(1)
                            # Clear the cache, because get_participants is cached and must be reread
                            get_participants.clear()
                            init_session_state()
                            st.session_state["users_selectbox_selected"] = (
                                display_name
                            )
                            st.rerun()  # to render the user selectbox new.


def init_session_state():
    """Initializes the session state variables (dicts) users_all_users and users_all_org_units"""
    users = get_participants(ParticipantType.HUMAN, False)
    set_users_into_session_state(users, "users_all_users")

    org_units = get_participants(ParticipantType.ORG_UNIT, True)
    set_org_units_into_session_state(org_units, "users_all_org_units")

    roles = get_participants(ParticipantType.ROLE, False)
    roles = [
        r for r in roles if r.name in APP_ROLES or r.name == "PUBLIC"
    ]  # remove the ones we  do not want
    set_roles_into_session_state(roles, "users_all_roles")


def render_user_selectbox() -> Optional[Participant]:

    show_only_active = st.toggle(label="Show only active", value=True)
    if show_only_active:
        usernames = sorted(
            [
                v["display_name"]
                for v in st.session_state.users_all_users.values()
                if v["state"] == "ACTIVE"
            ]
        )
    else:
        usernames = sorted(st.session_state.users_all_users.keys())

    key = "users_selectbox"
    selected_key = key + "_selected"
    if (
        selected_key in st.session_state
        and st.session_state[selected_key]
        and st.session_state[selected_key] in usernames
    ):
        index = usernames.index(st.session_state[selected_key])
    else:
        index = 0

    selected = st.selectbox(
        label="Select a user",
        options=usernames,
        key=key,
        index=index,
    )
    if selected:
        st.session_state[selected_key] = selected
        if selected_user := get_participant(
            st.session_state.users_all_users[selected]["id"]
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


def render_update_user_form(selected_user: Participant):
    """Renders the roles, groups and proxies and handles the save button"""
    enforcer = get_policy_enforcer()
    current_user = get_st_current_user()
    if not current_user:
        return

    disabled = not enforcer.enforce(current_user.username, "users", "write")

    if selected_user.state == ParticipantState.ACTIVE:
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
    st.text_input(
        label="Account Name", value=selected_user.name, disabled=True
    )
    display_name = st.text_input(
        label="Display Name",
        value=selected_user.display_name,
        disabled=disabled,
    )

    description = st.text_input(
        label="Description", value=selected_user.description, disabled=disabled
    )

    with st.form(key="update_user_form", clear_on_submit=False, border=False):
        scol1, scol2, scol3 = st.columns(3)
        with scol1:
            selected_roles = render_roles(
                "### Roles", selected_user, disabled=disabled
            )
        with scol2:
            selected_org_units = render_org_units(
                "### Member of", selected_user, disabled=disabled
            )
        with scol3:
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
                user_changes: dict[str, Any] = dict()
                if selected_user.description != description:
                    user_changes["description"] = description
                if selected_user.display_name != display_name:
                    user_changes["display_name"] = display_name
                if state_toggle != str(selected_user.state):
                    user_changes["state"] = state_toggle

                try:
                    updated = save_user_changes(
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
                    if updated:
                        pati_repo.commit()
                        st.success(
                            f"User {selected_user.display_name!a} updated"
                        )
                        time.sleep(1)
                        get_participants.clear()  # To reread the changes.
                        init_session_state()
                        st.rerun()
                    else:
                        st.info("No changes to save")
                        time.sleep(1)


def render_users():
    """Renders the Users dialog"""
    init_session_state()
    current_user = get_st_current_user()
    if not current_user:
        return
    with st.container(border=True):
        st.write("## Users")
        selected_user = render_user_selectbox()
        if not selected_user:
            st.stop()

        render_update_user_form(selected_user)
    enforcer = get_policy_enforcer()
    if enforcer.enforce(current_user.username, "users", "create"):
        st.divider()
        render_create_user_form("## Create User")


def render_user_registration_form(title: str):
    """Renders the roles, groups and proxies and handles the save button"""
    st.write(title)
    st.write(
        ":red[You are not authorized to use this application, but you can register yourself below]"
    )
    with st.form(key="user_registration_form", clear_on_submit=False):
        # We take the information from st.session_state.login_user because this user is not authorized in our system
        if login_user := st.session_state.get("login_user", None):
            account_name = st.text_input(
                label="Enterprise ID",
                value=login_user["sAMAccountName"].upper(),
                disabled=True,  # We don't want the manager to create an account for somebody else.
            )
            display_name = st.text_input(
                label="Display Name", value=login_user["displayName"]
            )
            email = st.text_input(
                label="Email", value=login_user["userPrincipalName"]
            )
            job_title = st.text_input(
                label="Job Title", value=login_user["title"]
            )

            st.divider()
            conditions_accepted = st.checkbox(
                label="I confirm that I'm authorized to access this application",
                value=False,
                key="users_user_terms_accepted_checkbox",
            )
            if st.form_submit_button(
                "Register",
                #                disabled=not st.session_state[
                #                    "users_user_terms_accepted_checkbox"
                #                ],
            ):
                if conditions_accepted:
                    if not validate_email(email):
                        st.error(f"Invalid Email: {email!a}")
                        st.stop()
                    if account_name != login_user["sAMAccountName"].upper():
                        st.error(
                            "You cannot create an account for someone else"
                        )
                        st.stop()
                    if send_user_registration_request(
                        account_name=account_name,
                        display_name=display_name,
                        email=email,
                        job_title=job_title,
                    ):
                        st.success("Registration request send")
                else:
                    st.error("Please accept terms and conditions")
                    st.stop()

        else:
            st.error("Oops! Something went wrong")
            st.stop()


def render_self_registration_form(title: str):
    """Self service for managers to create themselves as users"""
    st.write(title)
    st.write(
        ":red[You are not authorized to use this application, but you can register yourself below]"
    )
    with st.form(key="register_manager_form", clear_on_submit=False):
        # We take the information from st.session_state.login_user because this user is not authorized in our system
        if login_user := st.session_state.get("login_user", None):
            account_name = st.text_input(
                label="EnterpriseID",
                value=login_user["sAMAccountName"].upper(),
            )
            display_name = st.text_input(
                label="Display Name", value=login_user["displayName"]
            )
            email = st.text_input(
                label="Email", value=login_user["userPrincipalName"]
            )
            job_title = st.text_input(
                label="Job Title", value=login_user["title"]
            )

            st.divider()
            conditions_accepted = st.checkbox(
                label="I confirm that I am authorized to access this application",
                value=False,
                key="users_user_terms_accepted_checkbox",
            )
            if st.form_submit_button(
                "Register",
                #                disabled=not st.session_state[
                #                    "users_user_terms_accepted_checkbox"
                #                ],
            ):
                if conditions_accepted:
                    init_session_state()  # Make sure we have the roles in the session state
                    if not validate_email(email):
                        st.error(f"Invalid Email: {email!a}")
                    account_name = account_name.upper()
                    if account_name != login_user[
                        "sAMAccountName"
                    ].upper() and not is_administrator(
                        login_user["sAMAccountName"].upper()
                    ):
                        st.error(
                            "You cannot create an account for someone else"
                        )
                        st.stop()

                    create = ParticipantCreate(
                        name=account_name,
                        display_name=display_name,
                        email=email,
                        participant_type=ParticipantType.HUMAN,
                        created_by=login_user["sAMAccountName"],
                        description=job_title,
                    )

                    with ParticipantRepository(get_db()) as pati_repo:

                        try:
                            new_pati = pati_repo.create(create)
                            add_roles(
                                pati_repo,
                                new_pati,
                                [AppRoles.METADATA_MAINTAINER],
                            )

                        except Exception as e:
                            logger.exception(e)
                            st.exception(e)
                            raise
                        else:
                            enforcer = get_policy_enforcer()
                            enforcer.add_role_for_user(
                                account_name, AppRoles.METADATA_MAINTAINER
                            )
                            pati_repo.commit()
                            st.balloons()
                            st.success(
                                f"User {account_name} was successfully created. Please logout and login again!"
                            )
                        st.session_state["must_register"] = False
                else:
                    st.error("Please accept terms and conditions")
                    st.stop()

        else:
            st.error("Oops! Something went wrong")
            st.stop()


def send_user_registration_request(
    *, account_name: str, display_name: str, email: str, job_title: str
):
    email_to = "support@acme.com"
    message = f"""
--- Message send via UI from {display_name} <{email}>
Click "reply" to answer the user.

USER REGISTRATION REQUEST FOR UI:

Username: {account_name}
Display Name: {display_name}
Email: {email}
Job Title: {job_title}

"""
    st.error("Mail not implemented")
    return True
