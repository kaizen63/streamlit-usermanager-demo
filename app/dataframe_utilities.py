"""Utilities for dataframes"""

import logging
import re
from typing import Literal, TypeAlias

import pandas as pd
import streamlit as st
from common import safe_index
from config import settings

LabelVisibilityType: TypeAlias = Literal["visible", "hidden", "collapsed"]

logger = logging.getLogger(settings.LOGGER_NAME)


class MissingKeyPrefixError(Exception):
    pass


def reformat_path(input_path: str) -> str:
    """Replaces slash, backslash and colon with underscore"""
    return re.sub(r"[/\\:]", "_", input_path)


# @st.cache_data(show_spinner=False)
def split_dataframe(input_df: pd.DataFrame, rows: int) -> list[pd.DataFrame]:
    """Splits a dataframe in a list of dataframe with rows size"""
    df = [input_df.loc[i : i + rows - 1, :] for i in range(0, len(input_df), rows)]
    return df


def render_filter_menu(
    df: pd.DataFrame,
    *,
    exclude_columns: list[str] | None = None,
    label: str = "Filter By",
    label_visibility: LabelVisibilityType = "visible",
    key_prefix: str,
    select_column: str | None = None,
) -> pd.DataFrame:
    """
    Renders the filter menu and values menu.

    Returns the filtered dataframe if filtering is enabled.
    key_prefix must be a unique key for the filter. If not provided we create one.
    """
    filter_menu = st.columns(3)
    if exclude_columns is None:
        exclude_columns = []
    if not key_prefix:
        raise MissingKeyPrefixError
    key1 = f"{key_prefix}_name"
    key2 = f"{key_prefix}_values"

    columns = sorted([c for c in df.columns if c not in exclude_columns])
    index = safe_index(columns, select_column, 0)

    with filter_menu[0]:
        filter_field = st.selectbox(
            label,
            options=columns,
            key=key1,
            index=index,
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
            df = df[df[filter_field].isin(filter_values)].reset_index(drop=True)
    return df


def key_function(col: pd.Series) -> pd.Series:
    """Returns the sorting key function based on column type."""
    return col if pd.api.types.is_datetime64_any_dtype(col) else col.str.lower()


def render_sort_menu(
    df: pd.DataFrame,
    key_prefix: str,
    exclude_columns: list[str] | None = None,
) -> pd.DataFrame:
    """
    Renders the sort menu.

    Returns a sorted df if sorting is enabled.
    key_prefix: Unique prefix for the elements in thi sort menu box
    """

    def generate_key(suffix: str) -> str:
        return f"{key_prefix}_{suffix}"

    sort_menu = st.columns(3)
    if exclude_columns is None:
        exclude_columns = []
    if not key_prefix:
        raise MissingKeyPrefixError

    key1 = generate_key("filter_sort_radio")
    key2 = generate_key("sort_select")
    key3 = generate_key("sort_direction")

    columns = sorted([c for c in df.columns if c not in exclude_columns])

    with sort_menu[0]:
        sort = st.radio(
            "Sort",
            options=("Yes", "No"),
            horizontal=True,
            index=1,
            key=key1,
        )
    if sort == "Yes":
        with sort_menu[1]:
            sort_column = st.selectbox("Sort By", options=columns, key=key2)
        with sort_menu[2]:
            sort_direction = st.radio(
                "Direction",
                options=["⬆️", "⬇️"],
                horizontal=True,
                key=key3,
            )

        df = df.sort_values(
            by=sort_column,
            ascending=sort_direction == "⬆️",
            ignore_index=True,
            key=key_function,
            na_position="last",
        )
    return df


def calculate_total_pages(total_size: int, page_size: int) -> int:
    """Calculates how many pages we have to display"""
    return (total_size + page_size - 1) // page_size


def render_pagination_menu(df: pd.DataFrame, key_prefix: str) -> tuple[int, int]:
    """
    Renders the bottom menu with page count and batch size.

    Returns:
         current_page, batch_size

    """

    def generate_key(suffix: str) -> str:
        return f"{key_prefix}_{suffix}"

    if not key_prefix:
        raise MissingKeyPrefixError
    key1 = generate_key("page_size")
    key2 = generate_key("page_number")

    pagination_menu = st.columns((4, 1, 1))
    with pagination_menu[2]:
        batch_size_selected: str = st.selectbox(
            "Page Size",
            options=["10", "25", "50", "100", "all"],
            key=key1,
        )
    with pagination_menu[1]:
        page_size: int = (
            len(df) if batch_size_selected == "all" else int(batch_size_selected)
        )
        total_pages = calculate_total_pages(len(df), page_size)

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
    return current_page, page_size


def calculate_height(df: pd.DataFrame, page_size: int) -> int:
    """Calculates the height in pixel of the df. Note this is more an estimate."""
    h = int(35.0 * min([page_size + 1, len(df) + 1])) + 30
    # logger.debug(f"len(df)={len(df)}, {page_size=} -> {h=}")
    return h


def paginate_df(df: pd.DataFrame, key_prefix: str) -> tuple[pd.DataFrame, int]:
    """Renders pagination and returns the displayed dataframe and the page size"""
    current_page, page_size = render_pagination_menu(df, key_prefix)
    pages = split_dataframe(df, page_size)
    return (
        pd.DataFrame(pages[current_page - 1] if len(pages) else []),
        page_size,
    )
