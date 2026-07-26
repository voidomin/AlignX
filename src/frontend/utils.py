from pathlib import Path

import streamlit as st


def load_css() -> None:
    """
    Load custom CSS styles from static/style.css.
    Implicitly injects the CSS into the Streamlit app.
    """
    css_file = Path("static/style.css")
    if css_file.exists():
        with open(css_file) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
