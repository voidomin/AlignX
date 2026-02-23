import streamlit as st
import pandas as pd
from typing import List, Any
from examples.protein_sets import EXAMPLES

def render_input_section(pdb_manager: Any):
    """
    Render the PDB input section (IDs, Upload, Examples).
    """
    with st.container():
        # Use tabs for different input methods
        tab_input, tab_upload, tab_example = st.tabs(["✍️ Enter IDs", "📂 Upload Files", "🧪 Load Example"])
        
        # --- Tab 1: Direct Text Input ---
        with tab_input:
            pdb_input = st.text_input(
                "Enter PDB IDs (comma-separated)", 
                placeholder="e.g., 1L2Y, 1A6M, 1BKV",
                help="Enter 4-letter PDB codes. The tool handles fetching and cleaning automatically.",
                key="input_pdb_text_dashboard"
            )
            if pdb_input:
                # Basic parsing
                raw_ids = [pid.strip().upper() for pid in pdb_input.split(",") if pid.strip()]
                if raw_ids != st.session_state.pdb_ids:
                     st.session_state.pdb_ids = raw_ids
                     st.session_state.metadata_fetched = False # Reset metadata on change
        
        # --- Tab 2: File Upload ---
        with tab_upload:
            uploaded_files = st.file_uploader(
                "Upload .pdb files", 
                accept_multiple_files=True,
                type=['pdb'],
                help="Upload local structure files for analysis."
            )
            if uploaded_files:
                # Logic to handle uploaded files
                new_ids = []
                for uploaded_file in uploaded_files:
                    success, msg, path = pdb_manager.save_uploaded_file(uploaded_file)
                    if success:
                        new_ids.append(path.stem)
                    else:
                        st.error(f"Failed to save {uploaded_file.name}: {msg}")
                
                if new_ids:
                    st.info(f"Loaded {len(new_ids)} files: {', '.join(new_ids)}")
                    # Update state if new files loaded
                    current_ids = set(st.session_state.pdb_ids)
                    current_ids.update(new_ids)
                    st.session_state.pdb_ids = list(current_ids)
                    st.session_state.metadata_fetched = False

        # --- Tab 3: Examples ---
        with tab_example:
            # Use EXAMPLES from examples.protein_sets
            example_names = ["Select an example..."] + list(EXAMPLES.keys())
            selected_example = st.selectbox("Choose a dataset:", example_names)
            
            if selected_example != "Select an example...":
                if st.button(f"Load {selected_example}"):
                    st.session_state.pdb_ids = EXAMPLES[selected_example]
                    st.session_state.metadata_fetched = False
                    st.rerun()
