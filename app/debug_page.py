"""To display the debug page"""

import json
import logging

import streamlit as st
from common import check_access, filter_list
from config import settings

logger = logging.getLogger(settings.LOGGER_NAME)


def render_debug_page() -> None:
    """Render the debug page"""

    st.write("## Session State")
    session_state = dict(st.session_state.items())

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
    if check_access(st.session_state.current_user["username"], "settings", "read"):
        st.write("## Application Settings")
        fields = settings.model_fields.keys()
        # Do not show sensitive information
        exclude_keywords = (
            "PASSWORD",
            "SECRET",
            "KEY",
            "USERNAME",
            "CLIENT_ID",
            "TENANT",
        )
        # exclude_keywords = tuple()
        include_fields = filter_list(fields, exclude_keywords)
        # logger.debug(f"Include fields: {include_fields}")
        st.json(
            settings.model_dump_json(
                indent=4,
                include=include_fields,
            ),
            expanded=False,
        )
        # st.write("## Client Info")
        # st.write(f"Remote IP: {get_remote_ip()}")

        # user = st.experimental_user.to_dict()
        # st.json(
        #    body=json.dumps(
        #        user,
        #        indent=4,
        #        sort_keys=True,
        #        ensure_ascii=False,
        #        default=str,
        #    ),
        #    expanded=False,
        # )
