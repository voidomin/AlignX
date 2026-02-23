import streamlit as st
from examples.protein_sets import EXAMPLES

from typing import Callable

def render_sidebar(load_run_callback: Callable[[str], None]) -> None:
    """
    Render the sidebar configuration and history.
    
    Args:
        load_run_callback: Function to call when loading a run from history.
                           Takes a run_id (str) as argument.
    """
    with st.sidebar:
        st.header("⚙️ Setup")
        
        mustang_ok, mustang_msg = st.session_state.mustang_install_status
        if mustang_ok:
            st.success(f"✓ {mustang_msg}")
        else:
            st.error(f"✗ {mustang_msg}")
            st.info("See WINDOWS_SETUP.md for installation instructions")

        # System Diagnostics
        with st.expander("🛠️ System Health", expanded=False):
            if st.button("🔍 Run Diagnostics", use_container_width=True):
                with st.spinner("Checking dependencies..."):
                    results = st.session_state.system_manager.run_diagnostics()
                    st.session_state.diag_results = results
            
            if 'diag_results' in st.session_state:
                res = st.session_state.diag_results
                col_a, col_b = st.columns(2)
                with col_a:
                    st.write("**Mustang**")
                    if res["Mustang"]["status"] == "PASSED":
                        st.success("OK")
                    else:
                        st.error("FAIL")
                with col_b:
                    st.write("**R (Bio3D)**")
                    if res["R environment"]["status"] == "PASSED":
                        st.success("OK")
                    else:
                        st.warning("MISSING")
                
                st.caption(f"OS: {res['Platform']}")
                st.caption(f"Py: {res['Python Version']}")
                
                if st.button("🧹 Clear Logs", use_container_width=True, type="secondary"):
                    st.session_state.system_manager.cleanup_old_runs(days=0) # Clear all temp/old
                    st.success("Temporary files cleared.")
        
        st.divider()

        # History Section
        with st.expander("📜 History", expanded=False):
            # Limit to latest 6 runs
            try:
                runs = st.session_state.history_db.get_all_runs(limit=6)
            except TypeError:
                runs = st.session_state.history_db.get_all_runs()[:6]
                
            if not runs:
                st.info("No saved runs found.")
            else:
                for run in runs:
                    with st.container():
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            st.caption(f"**{run['name']}**")
                            st.caption(f"🕒 {run['timestamp']}")
                        with col2:
                            if st.button("📂", key=f"load_{run['id']}", help="Load this run"):
                                load_run_callback(run['id'])
                        
                        if st.button("🗑️ Delete", key=f"del_{run['id']}", use_container_width=True):
                            if st.session_state.history_db.delete_run(run['id']):
                                st.rerun()
                        st.divider()
                
                if st.button("🗑️ Clear All History", use_container_width=True, type="secondary"):
                    for run in runs:
                        st.session_state.history_db.delete_run(run['id'])
                    st.rerun()
        
        st.divider()
        st.info("👈 Use the main dashboard to enter PDB IDs or upload files.")
        
        # Guided Mode Toggle
        st.session_state.guided_mode = st.toggle(
            "🎓 Guided Mode", 
            value=st.session_state.guided_mode,
            help="Enable interactive explanations for each result tab."
        )
        
        # Advanced options
        with st.expander("⚙️ Advanced Options"):
            st.checkbox("Filter large files", value=True,
                        help="Automatically suggest chain extraction for large PDB files")
            
            st.session_state.remove_water = st.checkbox("Remove water molecules", value=st.session_state.remove_water)
            st.session_state.remove_hetero = st.checkbox("Remove heteroatoms", value=st.session_state.remove_hetero)
            
            st.markdown("**Chain Selection**")
            chain_selection = st.radio(
                "How to handle multi-chain structures?",
                ["Auto (use first chain)", "Specify chain ID"],
                help="GPCRs and other proteins may have multiple chains. Choose how to handle them.",
                index=0 if st.session_state.chain_selection_mode == "Auto (use first chain)" else 1
            )
            
            selected_chain = st.session_state.selected_chain
            if chain_selection == "Specify chain ID":
                selected_chain = st.text_input(
                    "Chain ID",
                    value=st.session_state.selected_chain,
                    max_chars=1,
                    help="Enter chain identifier (e.g., A, B, C)"
                ).strip().upper()
            
            st.session_state.chain_selection_mode = chain_selection
            st.session_state.selected_chain = selected_chain
        
        # Version badge — read from config for single source of truth
        version = st.session_state.config.get('app', {}).get('version', '?.?.?')
        st.caption(f"🧬 **Mustang Pipeline** `v{version}`")
