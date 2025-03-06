"""Interface to participants"""

import logging
from typing import Callable, Literal, TypeAlias

import streamlit as st
from codetiming import Timer
from config import settings
from db import get_db
from humanfriendly import format_timespan
from participants import (
    Participant,
    ParticipantRepository,
    ParticipantType,
    ParticipantState,
)
from who_called_me import who_called_me

logger = logging.getLogger(settings.LOGGER_NAME)


@st.cache_data(ttl=600, show_spinner="Loading users...")
def get_users(
    *,
    only_active: bool,
    include_relations: bool = False,
) -> list[Participant]:
    """Get a list of all users"""
    with Timer(
        name="get_users",
        text=lambda sec: f"Get users from database {only_active=} {include_relations=} - caller={who_called_me(6)}: "
        f"{format_timespan(sec)}",
        logger=logger.debug,
    ):
        with ParticipantRepository(get_db()) as pati_repo:
            users: list[Participant] = pati_repo.get_all(
                ParticipantType.HUMAN,
                include_relations=include_relations,
                only_active=only_active,
            )
            return users


@st.cache_data(ttl=600, show_spinner="Loading roles...")
def get_roles(
    *,
    only_active: bool,
    include_relations: bool = False,
) -> list[Participant]:
    """Get a list of all rolo"""
    with Timer(
        name="get_roles",
        text=lambda sec: f"Get roles from database {only_active=} {include_relations=} - caller={who_called_me(6)}: "
        f"{format_timespan(sec)}",
        logger=logger.debug,
    ):
        with ParticipantRepository(get_db()) as pati_repo:
            roles: list[Participant] = pati_repo.get_all(
                ParticipantType.ROLE,
                include_relations=include_relations,
                only_active=only_active,
            )
            return roles


@st.cache_data(ttl=600, show_spinner="Loading org_units...")
def get_org_units(
    *,
    only_active: bool,
    include_relations: bool = False,
) -> list[Participant]:
    """Get a list of all org_units"""
    with Timer(
        name="get_org_units",
        text=lambda sec: f"Get org_units from database {only_active=} {include_relations=} - caller={who_called_me(6)}: "
        f"{format_timespan(sec)}s",
        logger=logger.debug,
    ):
        with ParticipantRepository(get_db()) as pati_repo:
            roles: list[Participant] = pati_repo.get_all(
                ParticipantType.ORG_UNIT,
                include_relations=include_relations,
                only_active=only_active,
            )
            return roles


def get_lookup_by_display_name(
    participants: list[Participant],
) -> dict[str, Participant]:
    """Returns a dictionary with key display_name and value Participant"""
    return {p.display_name: p for p in participants}


def get_lookup_by_name(
    participants: list[Participant],
) -> dict[str, Participant]:
    """Returns a dictionary with key display_name and value Participant"""
    return {p.name: p for p in participants}


def get_participant(
    pati_id: int, include_relations: bool = True, include_proxies: bool = True
) -> Participant | None:
    """Get a participant by its id. Can be of all types of participants"""

    with ParticipantRepository(get_db()) as pati_repo:
        participant: Participant | None = pati_repo.get_by_id(
            pati_id,
            include_relations=include_relations,
            include_proxies=include_proxies,
        )
        return participant


# DO NOT CACHE
def get_participant_by_name(
    name: str,
    participant_type: ParticipantType,
    *,
    include_relations: bool = False,
    include_proxies: bool = False,
) -> Participant | None:
    """Returns the participant who maintained the change or created the app"""
    try:
        with ParticipantRepository(get_db()) as repo:
            pati = repo.get_by_name(
                name,
                participant_type,
                include_relations=include_relations,
                include_proxies=include_proxies,
            )
    except Exception as e:
        logger.exception(f"Cannot find {name} in users {e}")
        return None
    else:
        return pati


# DO NOT CACHE
def get_participant_by_display_name(
    display_name: str,
    participant_type: ParticipantType,
    *,
    include_relations: bool = False,
    include_proxies: bool = False,
) -> Participant | None:
    """Returns the participant who maintained the change or created the app"""
    try:
        with ParticipantRepository(get_db()) as repo:
            pati = repo.get_by_display_name(
                display_name,
                participant_type,
                include_relations=include_relations,
                include_proxies=include_proxies,
            )
    except Exception as e:
        logger.exception(f"Cannot find {display_name} in users {e}")
        return None
    else:
        return pati


def get_user_display_name(name: str | None) -> str | None:
    """Returns the display_name for a participant name. Returns the input if the
    participant is not in the table.
    """
    if not name:
        return name
    pati = get_participant_by_name(name, ParticipantType.HUMAN)
    return pati.display_name if pati else name


IdentifierType: TypeAlias = Literal["name", "display_name"]


def get_participant_ids(
    participant_type: ParticipantType,
    identifier_type: IdentifierType,
    identifiers: list[str],
) -> list[int]:
    """Returns the participant ids of the participants by the identifier type"""
    participant_fetchers: dict[
        ParticipantType, Callable[..., list[Participant]]
    ] = {
        ParticipantType.HUMAN: get_users,
        ParticipantType.ROLE: get_roles,
        ParticipantType.ORG_UNIT: get_org_units,
    }

    if participant_type not in participant_fetchers:
        raise ValueError(f"Invalid ParticipantType: {participant_type}")
    participants = participant_fetchers[participant_type](
        only_active=False, include_relations=False
    )
    ids = [
        p.id
        for p in participants
        if (p.display_name if identifier_type == "display_name" else p.name)
        in identifiers
    ]
    return ids


def check_pati_exists(
    pati_repo: ParticipantRepository,
    participant_type: ParticipantType,
    name: str,
    display_name: str,
) -> bool:
    """Checks if the participant exists by name or display name, whether active or terminated.
    Returns True if the user already exists, False otherwise."""

    def pati_exists(field: str, value: str) -> bool:
        exists = pati_repo.exists(field, value, participant_type)
        if exists:
            status_msg = (
                "but is not active"
                if exists == ParticipantState.TERMINATED
                else ""
            )
            st.error(
                f"{field.replace('_', ' ').title()}: {value!a} already exists {status_msg}".strip()
            )
        return bool(exists)

    return pati_exists("name", name) or pati_exists(
        "display_name", display_name
    )
