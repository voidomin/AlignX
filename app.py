import os
import sys

# Set working directory to the app directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))
if os.getcwd() not in sys.path:
    sys.path.insert(0, os.getcwd())

import matplotlib

matplotlib.use("Agg")

import streamlit as st

# Backend Imports (for initialization)

# Utility Imports
from src.utils.session_manager import SessionInitializer

# Frontend Modules
from src.frontend import utils, sidebar, analysis

# Page configuration
st.set_page_config(
    page_title="Mustang Structural Alignment Pipeline",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_session_state():
    """Initialize Streamlit session state variables via the SessionInitializer."""
    # 1. Core Initialization
    SessionInitializer.initialize()

    # 2. Auto-recovery: If results is None, try to load the latest successful run
    # ONLY if we haven't already attempted recovery in this session
    if st.session_state.get("results") is None and not st.session_state.get(
        "auto_recovered", False
    ):
        st.session_state.auto_recovered = True  # Mark as attempted (session-persistent)
        st.session_state.loading_latest = True

        session_id = st.session_state.get("session_id")
        latest_run = st.session_state.history_db.get_latest_run(session_id=session_id)

        if latest_run:
            analysis.load_run_from_history(latest_run["id"], is_auto=True)
        st.session_state.loading_latest = False


def main():
    """Main application function."""
    # 1. Initialize State
    init_session_state()

    # 2. Load Global CSS
    utils.load_css()

    # 3. Header
    st.markdown(
        '<p class="main-header">🧬 Mustang Structural Alignment Pipeline</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="sub-header">Automated Multiple Structural Alignment for Any Protein Family</p>',
        unsafe_allow_html=True,
    )

    # 4. Render Sidebar (passing callback for history loading)
    sidebar.render_sidebar(analysis.load_run_from_history)

    # 5. Main Content Logic (Mission Control)
    analysis.render_dashboard()


if __name__ == "__main__":
    main()
