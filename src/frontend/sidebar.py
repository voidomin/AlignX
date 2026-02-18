import streamlit as st
from examples.protein_sets import EXAMPLES

def render_sidebar(load_run_callback):
    """
    Render the sidebar configuration and history.
    
    Args:
        load_run_callback: Function to call when loading a run from history.
    """
    with st.sidebar:
        st.header("⚙️ Setup")
        
        # Check Mustang installation
        mustang_ok, mustang_msg = st.session_state.mustang_runner.check_installation()
        if mustang_ok:
            st.success(f"✓ {mustang_msg}")
        else:
            st.error(f"✗ {mustang_msg}")
            st.info("See WINDOWS_SETUP.md for installation instructions")
        
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
        
        st.divider()
        st.info("👈 Use the main dashboard to enter PDB IDs or upload files.")
        
        st.divider()
        
        # Advanced options
        with st.expander("⚙️ Advanced Options"):
            filter_chains = st.checkbox("Filter large files", value=True,
                                       help="Automatically suggest chain extraction for large PDB files")
            
            remove_water = st.checkbox("Remove water molecules", value=True)
            remove_hetero = st.checkbox("Remove heteroatoms", value=True)
            
            st.markdown("**Chain Selection**")
            chain_selection = st.radio(
                "How to handle multi-chain structures?",
                ["Auto (use first chain)", "Specify chain ID"],
                help="GPCRs and other proteins may have multiple chains. Choose how to handle them."
            )
            
            selected_chain = None
            if chain_selection == "Specify chain ID":
                selected_chain = st.text_input(
                    "Chain ID",
                    value="A",
                    max_chars=1,
                    help="Enter chain identifier (e.g., A, B, C)"
                ).strip().upper()
            
            # Store in session state
            st.session_state.chain_selection_mode = chain_selection
            st.session_state.selected_chain = selected_chain
