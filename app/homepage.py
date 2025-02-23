"""Render homepage"""

import logging
from enum import StrEnum

import pandas as pd
import streamlit as st
from config import settings
from dataframe_utilities import (
    calculate_height,
    paginate_df,
    render_filter_menu,
    render_sort_menu,
)
from db import get_db
from participants import Participant, ParticipantRepository

logger = logging.getLogger(settings.LOGGER_NAME)


class ParticipantsTableHeader(StrEnum):
    ID = "Id"
    NAME = "Name"
    DISPLAY_NAME = "DisplayName"
    PARTICIPANT_TYPE = "PatiType"
    EMAIL = "Email"
    EXTERNAL_REFERENCE = "ExternalReference"
    STATE = "State"
    CREATED_BY = "CreatedBy"
    CREATED_TIMESTAMP = "CreatedTime"
    UPDATED_BY = "UpdatedBy"
    UPDATED_TIMESTAMP = "UpdatedTime"
    DESCRIPTION = "Description"


def get_participants_data() -> pd.DataFrame | None:
    """Returns the participants table data"""

    with ParticipantRepository(get_db()) as repo:
        humans: list[Participant] = repo.get_all(
            "HUMAN", include_relations=False
        )
        org_units: list[Participant] = repo.get_all(
            "ORG_UNIT", include_relations=False
        )
        roles: list[Participant] = repo.get_all(
            "ROLE", include_relations=False
        )
        all_participants: list[Participant] = humans + org_units + roles

    data = [
        d.model_dump(
            include={
                "id",
                "name",
                "display_name",
                "participant_type",
                "email",
                "description",
                "state",
                "created_by",
                "created_timestamp",
                "updated_by",
                "updated_timestamp",
            }
        )
        for d in all_participants
    ]
    if len(data) == 0:
        return None
    df = pd.DataFrame(data)
    df = df.rename(
        columns={
            "id": ParticipantsTableHeader.ID,
            "name": ParticipantsTableHeader.NAME,
            "display_name": ParticipantsTableHeader.DISPLAY_NAME,
            "participant_type": ParticipantsTableHeader.PARTICIPANT_TYPE,
            "email": ParticipantsTableHeader.EMAIL,
            "description": ParticipantsTableHeader.DESCRIPTION,
            "state": ParticipantsTableHeader.STATE,
            "created_by": ParticipantsTableHeader.CREATED_BY,
            "created_timestamp": ParticipantsTableHeader.CREATED_TIMESTAMP,
            "updated_by": ParticipantsTableHeader.UPDATED_BY,
            "updated_timestamp": ParticipantsTableHeader.UPDATED_TIMESTAMP,
        }
    )

    return df


def render_participants_table(title: str):
    """Render the participants table"""
    st.write(title)
    df = get_participants_data()
    if df is None or df.empty:
        return
    count = len(df)
    st.write(f"Participants: [{count}]")
    with st.container(border=True):
        df = render_filter_menu(
            df,
            exclude_columns=[
                ParticipantsTableHeader.CREATED_TIMESTAMP,
                ParticipantsTableHeader.UPDATED_TIMESTAMP,
            ],
            key_prefix="homepage_pati_filter",
        )
        df = render_sort_menu(df, key_prefix="homepage_pati_sort")
        st.write(f"[{len(df)}]")

    displayed_df, page_size = paginate_df(
        df, key_prefix="homepage_pati_paginate"
    )

    pagination = st.container(height=None)
    height = calculate_height(df, page_size)

    column_config = {
        ParticipantsTableHeader.ID: st.column_config.NumberColumn(
            format="%4f"
        ),
    }

    pagination.dataframe(
        data=displayed_df,
        use_container_width=True,
        height=height,
        hide_index=True,
        column_config=column_config,
        column_order=[
            ParticipantsTableHeader.ID,
            ParticipantsTableHeader.NAME,
            ParticipantsTableHeader.DISPLAY_NAME,
            ParticipantsTableHeader.PARTICIPANT_TYPE,
            ParticipantsTableHeader.EMAIL,
            ParticipantsTableHeader.DESCRIPTION,
            ParticipantsTableHeader.STATE,
            ParticipantsTableHeader.CREATED_BY,
            ParticipantsTableHeader.CREATED_TIMESTAMP,
            ParticipantsTableHeader.UPDATED_BY,
            ParticipantsTableHeader.UPDATED_TIMESTAMP,
        ],
    )


def render_homepage():
    """Renders the homepage"""
    st.write("## Welcome to Streamlit UserManager Demo")
    render_participants_table("## Participants")
