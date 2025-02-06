""" Utilities for dataframes"""

import pandas as pd
import streamlit as st

from who_called_me import who_called_me2
from typing import Literal
import re


def reformat_path(input_path: str):
    """Replaces slash, backslash and colon with underscore"""
    return re.sub(r"[/\\:]", "_", input_path)


# @st.cache_data(show_spinner=False)
def split_dataframe(input_df: pd.DataFrame, rows: int) -> list[pd.DataFrame]:
    """Splits a dataframe in a list of dataframe with rows size"""
    df = [
        input_df.loc[i : i + rows - 1, :]
        for i in range(0, len(input_df), rows)
    ]
    return df


def render_filter_menu(
    df: pd.DataFrame,
    *,
    exclude_columns: list[str] | None = None,
    label: str = "Filter By",
    label_visibility: Literal["visible", "hidden", "collapsed"] = "visible",
    key_prefix: str = None,
) -> pd.DataFrame:
    """Renders the filter menu and values menu. Returns the filtered dataframe if filtering is enabled.
    key_prefix must be a unique key for the filter. If not provided we create one.
    """
    filter_menu = st.columns(3)
    if exclude_columns is None:
        exclude_columns = []
    if not key_prefix:
        filename, line_no, function = who_called_me2()
        key1 = f"filter_select_{reformat_path(filename)}_{line_no}_{function}"
        key2 = f"filter_multiselect_{reformat_path(filename)}_{line_no}_{function}"
    else:
        key1 = f"{key_prefix}_1"
        key2 = f"{key_prefix}_2"

    columns = sorted([c for c in df.columns if c not in exclude_columns])
    with filter_menu[0]:
        filter_field = st.selectbox(
            label,
            options=columns,
            key=key1,
            label_visibility=label_visibility,
        )
    st.empty()
    with filter_menu[1]:
        filter_values = st.multiselect(
            "Select Values",
            sorted(df[filter_field].unique(), key=lambda x: (x is None, x)),
            key=key2,
            label_visibility=label_visibility,
        )
        if filter_values:
            df = df[df[filter_field].isin(filter_values)].reset_index(
                drop=True
            )
    return df


def render_sort_menu(
    df: pd.DataFrame,
    exclude_columns: list[str] | None = None,
    key_prefix: str = None,
) -> pd.DataFrame:
    """Renders the sort menu and returns a sorted df if sorting is enabled.
    key_prefix: Unique prefix for the elements in thi sort menu box"""

    sort_menu = st.columns(3)
    if exclude_columns is None:
        exclude_columns = []
    if not key_prefix:
        filename, line_no, function = who_called_me2()
        key1 = (
            f"filter_sort_radio_{reformat_path(filename)}_{line_no}_{function}"
        )
        key2 = f"sort_select_{reformat_path(filename)}_{line_no}_{function}"
        key3 = f"sort_direction_{reformat_path(filename)}_{line_no}_{function}"
    else:
        key1 = f"{key_prefix}_1"
        key2 = f"{key_prefix}_2"
        key3 = f"{key_prefix}_3"

    columns = sorted([c for c in df.columns if c not in exclude_columns])

    with sort_menu[0]:
        sort = st.radio(
            "Sort",
            options=["Yes", "No"],
            horizontal=1,
            index=1,
            key=key1,
        )
    if sort == "Yes":
        with sort_menu[1]:
            sort_field = st.selectbox("Sort By", options=columns, key=key2)
        with sort_menu[2]:
            sort_direction = st.radio(
                "Direction",
                options=["⬆️", "⬇️"],
                horizontal=True,
                key=key3,
            )
        df = df.sort_values(
            by=sort_field,
            ascending=sort_direction == "⬆️",
            ignore_index=True,
        )
    return df


def render_pagination_menu(
    df: pd.DataFrame, key_prefix: str = None
) -> tuple[int, int]:
    """Renders the bottom menu with page count and batch size.
    Returns:
         current_page, batch_size
    """
    filename, line_no, function = who_called_me2()
    if not key_prefix:
        key1 = (
            f"pagination_select_{reformat_path(filename)}_{line_no}_{function}"
        )
        key2 = f"page_input_{reformat_path(filename)}_{line_no}_{function}"
    else:
        key1 = f"{key_prefix}_1"
        key2 = f"{key_prefix}_2"

    pagination_menu = st.columns((4, 1, 1))
    with pagination_menu[2]:
        batch_size_str = st.selectbox(
            "Page Size",
            options=["10", "25", "50", "100", "all"],
            key=key1,
        )
    with pagination_menu[1]:
        batch_size = (
            len(df) if batch_size_str == "all" else int(batch_size_str)
        )
        total_pages = (
            int(len(df) / batch_size) + 1
            if int(len(df) / batch_size) > 0 and len(df) > batch_size
            else 1
        )

        current_page = st.number_input(
            "Page",
            min_value=1,
            max_value=total_pages,
            step=1,
            key=key2,
        )
    with pagination_menu[2]:
        st.markdown(
            f"Page **{current_page}** of **{total_pages}**",
        )
    return current_page, batch_size


def calculate_height(df: pd.DataFrame, page_size: int) -> int:
    """Calculates the height in pixel of the df. Note this is more an estimate."""
    h = int(37 * min([page_size, len(df) + 1, 100]))
    return h


def paginate_df(df: pd.DataFrame, key_prefix: str) -> tuple[pd.DataFrame, int]:
    """renders pagination and returns the displayed dataframe and the page size"""

    current_page, page_size = render_pagination_menu(df, key_prefix)
    pages = split_dataframe(df, page_size)
    return (
        pd.DataFrame(pages[current_page - 1] if len(pages) else []),
        page_size,
    )
