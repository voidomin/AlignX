import streamlit as st
from pathlib import Path

# Backend Imports (for initialization)
from src.backend.pdb_manager import PDBManager
from src.backend.mustang_runner import MustangRunner
from src.backend.rmsd_analyzer import RMSDAnalyzer
from src.backend.sequence_viewer import SequenceViewer
from src.backend.report_generator import ReportGenerator
from src.backend.ligand_analyzer import LigandAnalyzer
from src.backend.database import HistoryDatabase
from src.backend.utilities import SystemManager
from src.backend.coordinator import AnalysisCoordinator

# Utility Imports
from src.utils.logger import setup_logger
from src.utils.config_loader import load_config
from src.utils.cache_manager import CacheManager
from src.utils.session_manager import get_session_id, cleanup_stale_sessions

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
    """Initialize Streamlit session state variables."""
    if "config" not in st.session_state:
        st.session_state.config = load_config()
        st.session_state.logger, st.session_state.log_file = setup_logger()

    # Session isolation: generate a unique session ID per browser tab
    if "session_id" not in st.session_state:
        st.session_state.session_id = get_session_id()

    session_id = st.session_state.session_id

    if "history_db" not in st.session_state:
        st.session_state.history_db = HistoryDatabase()

    if "cache_manager" not in st.session_state:
        st.session_state.cache_manager = CacheManager(
            st.session_state.config, st.session_state.history_db
        )

    if "pdb_manager" not in st.session_state:
        st.session_state.pdb_manager = PDBManager(
            st.session_state.config, st.session_state.cache_manager,
            session_id=session_id,
        )

    if "mustang_runner" not in st.session_state:
        st.session_state.mustang_runner = MustangRunner(st.session_state.config)

    if "rmsd_analyzer" not in st.session_state:
        st.session_state.rmsd_analyzer = RMSDAnalyzer(st.session_state.config)

    if "sequence_viewer" not in st.session_state:
        st.session_state.sequence_viewer = SequenceViewer()

    if "report_generator" not in st.session_state:
        st.session_state.report_generator = ReportGenerator(
            Path("results") / "latest_run"
        )

    if "pdb_ids" not in st.session_state:
        st.session_state.pdb_ids = []

    if "results" not in st.session_state:
        st.session_state.results = None

    if "ligand_analyzer" not in st.session_state:
        st.session_state.ligand_analyzer = LigandAnalyzer(st.session_state.config)

    if "coordinator" not in st.session_state:
        st.session_state.coordinator = AnalysisCoordinator(
            st.session_state.config, session_id=session_id
        )

    if "auto_recovered" not in st.session_state:
        st.session_state.auto_recovered = False

        if "system_manager" not in st.session_state:
            st.session_state.system_manager = SystemManager(st.session_state.config)
            # Perform automated startup cleanup (runs older than 7 days)
            st.session_state.system_manager.cleanup_old_runs(days=7)
            # TTL cleanup: purge stale session directories (>24h)
            cleanup_stale_sessions(max_age_hours=24)

        # --- NEW CENTRALIZED STATE ---
        if "mustang_install_status" not in st.session_state:
            mustang_ok, mustang_msg = (
                st.session_state.mustang_runner.check_installation()
            )
            st.session_state.mustang_install_status = (mustang_ok, mustang_msg)

        if "guided_mode" not in st.session_state:
            st.session_state.guided_mode = False

        if "chain_selection_mode" not in st.session_state:
            st.session_state.chain_selection_mode = "Auto (use first chain)"

        if "selected_chain" not in st.session_state:
            st.session_state.selected_chain = "A"

        if "manual_chain_selections" not in st.session_state:
            st.session_state.manual_chain_selections = {}

        if "metadata_fetched" not in st.session_state:
            st.session_state.metadata_fetched = False

        if "metadata" not in st.session_state:
            st.session_state.metadata = {}

        if "remove_water" not in st.session_state:
            st.session_state.remove_water = True

        if "remove_hetero" not in st.session_state:
            st.session_state.remove_hetero = True

        if "input_method_radio" not in st.session_state:
            st.session_state.input_method_radio = "Manual Entry"

    # Auto-recovery: If results is None, try to load the latest successful run
    # ONLY if we haven't already attempted recovery in this session
    if st.session_state.get("results") is None and not st.session_state.auto_recovered:
        st.session_state.auto_recovered = True  # Mark as attempted (session-persistent)
        st.session_state.loading_latest = True
        latest_run = st.session_state.history_db.get_latest_run(
            session_id=st.session_state.get("session_id")
        )
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
