from pathlib import Path

import streamlit as st
from __init__ import __maintainer__, __title__, __version__


def render_about() -> None:
    st.write(
        f"### {__title__} - v{__version__} - Powered by [:streamlit:](https://streamlit.io)"
    )
    st.write(f"Maintainer: {__maintainer__}")

    with (
        st.container(height=800),
        Path("CHANGELOG.md").open("r", encoding="utf-8") as f,
    ):
        changelog = f.read()
        st.write(changelog, unsafe_allow_html=True)
