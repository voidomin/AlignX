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

# Frontend Modules
from src.frontend import utils, home, sidebar, analysis, results

# Page configuration
st.set_page_config(
    page_title="Mustang Structural Alignment Pipeline",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

def init_session_state():
    """Initialize Streamlit session state variables."""
    if 'config' not in st.session_state:
        st.session_state.config = load_config()
        st.session_state.logger, st.session_state.log_file = setup_logger()
    
    if 'pdb_manager' not in st.session_state:
        st.session_state.pdb_manager = PDBManager(st.session_state.config)
    
    if 'mustang_runner' not in st.session_state:
        st.session_state.mustang_runner = MustangRunner(st.session_state.config)
    
    if 'rmsd_analyzer' not in st.session_state:
        st.session_state.rmsd_analyzer = RMSDAnalyzer(st.session_state.config)
    
    if 'sequence_viewer' not in st.session_state:
        st.session_state.sequence_viewer = SequenceViewer()
        
    if 'report_generator' not in st.session_state:
        st.session_state.report_generator = ReportGenerator(Path('results') / 'latest_run')
    
    if 'pdb_ids' not in st.session_state:
        st.session_state.pdb_ids = []
    
    if 'results' not in st.session_state:
        st.session_state.results = None

    if 'ligand_analyzer' not in st.session_state:
        st.session_state.ligand_analyzer = LigandAnalyzer(st.session_state.config)
        
    if 'history_db' not in st.session_state:
        st.session_state.history_db = HistoryDatabase()

    if 'coordinator' not in st.session_state:
        st.session_state.coordinator = AnalysisCoordinator(st.session_state.config)

    if 'auto_recovered' not in st.session_state:
        st.session_state.auto_recovered = False
        
    if 'system_manager' not in st.session_state:
        st.session_state.system_manager = SystemManager(st.session_state.config)
        # Perform automated startup cleanup (runs older than 7 days)
        st.session_state.system_manager.cleanup_old_runs(days=7)
        
    # Auto-recovery: If results is None, try to load the latest successful run
    # ONLY if we haven't already attempted recovery in this session
    if st.session_state.get('results') is None and not st.session_state.auto_recovered:
        st.session_state.auto_recovered = True # Mark as attempted (session-persistent)
        st.session_state.loading_latest = True
        latest_run = st.session_state.history_db.get_latest_run()
        if latest_run:
            analysis.load_run_from_history(latest_run['id'], is_auto=True)
        st.session_state.loading_latest = False


def main():
    """Main application function."""
    # 1. Initialize State
    init_session_state()
    
    # 2. Load Global CSS
    utils.load_css()
    
    # 3. Header
    st.markdown('<p class="main-header">🧬 Mustang Structural Alignment Pipeline</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Automated Multiple Structural Alignment for Any Protein Family</p>', unsafe_allow_html=True)
    
    # 4. Render Sidebar (passing callback for history loading)
    sidebar.render_sidebar(analysis.load_run_from_history)
    
    # 5. Main Content Logic (Mission Control)
    analysis.render_dashboard()


if __name__ == "__main__":
    main()
