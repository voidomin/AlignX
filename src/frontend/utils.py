import streamlit as st
from pathlib import Path

def load_css():
    """Load custom CSS styles."""
    css_file = Path("static/style.css")
    if css_file.exists():
        with open(css_file) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
