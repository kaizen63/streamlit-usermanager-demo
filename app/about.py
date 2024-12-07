
import streamlit as st
from __init__ import __maintainer__, __title__, __version__
from contact import render_contact_form


@st.dialog("Contact Us")
def show_contact_form():
    render_contact_form()


def render_about() -> None:
    st.write(
        f"### {__title__} - v{__version__} - Powered by [:streamlit:](https://streamlit.io)"
    )
    st.write(f"Maintainer: {__maintainer__}")

    with st.container(height=800):
        with open("CHANGELOG.md", "r", encoding="utf-8") as f:
            changelog = f.read()
            st.write(changelog, unsafe_allow_html=True)

    return
