import streamlit as st
from typing import Any
from examples.protein_sets import EXAMPLES


def render_input_section(pdb_manager: Any):
    """
    Render the PDB/AlphaFold input section.
    """
    with st.container():
        # Use tabs for different input methods
        tab_input, tab_upload, tab_example = st.tabs(
            ["✍️ Smart Search", "📂 Upload Files", "🧪 Load Example"]
        )

        # --- Tab 1: Smart Search (PDB & AlphaFold) ---
        with tab_input:
            def on_pdb_input_change():
                pdb_input = st.session_state.input_pdb_text_dashboard
                if pdb_input:
                    raw_ids = [pid.strip() for pid in pdb_input.split(",") if pid.strip()]
                    clean_ids = []
                    for pid in raw_ids:
                        if pid.upper().startswith("AF-"):
                            clean_ids.append(pid)
                        else:
                            clean_ids.append(pid.upper())

                    if clean_ids != st.session_state.get("pdb_ids", []):
                        st.session_state.pdb_ids = clean_ids
                        st.session_state.metadata_fetched = False
                        st.session_state.metadata = {}

            pdb_input = st.text_input(
                "Enter IDs (PDB or AlphaFold)",
                placeholder="e.g., 1L2Y, AF-P12345-F1",
                help="Supports 4-letter PDB codes or AlphaFold identifiers. Comma-separated.",
                key="input_pdb_text_dashboard",
                on_change=on_pdb_input_change,
            )

            if pdb_input:
                af_detected = [
                    pid.strip() for pid in pdb_input.split(",") 
                    if pid.strip().upper().startswith("AF-")
                ]
                if af_detected:
                    st.caption(f"✨ **AlphaFold Detected**: {', '.join(af_detected)}")

        # --- Tab 2: File Upload ---
        with tab_upload:
            def on_file_upload():
                st.session_state.input_pdb_text_dashboard = ""

            uploaded_files = st.file_uploader(
                "Upload structure files (.pdb, .cif)",
                accept_multiple_files=True,
                type=["pdb", "cif"],
                help="Upload PDB or mmCIF files. They will be automatically standardized for alignment.",
                key="structure_file_uploader",
                on_change=on_file_upload,
            )
            if uploaded_files:
                new_ids = []
                for uploaded_file in uploaded_files:
                    success, msg, path = pdb_manager.save_uploaded_file(uploaded_file)
                    if success:
                        new_ids.append(path.stem)
                    else:
                        st.error(f"Failed to save {uploaded_file.name}: {msg}")

                if new_ids:
                    st.info(f"Loaded {len(new_ids)} files: {', '.join(new_ids)}")
                    current_ids = set(st.session_state.get("pdb_ids", []))
                    current_ids.update(new_ids)
                    st.session_state.pdb_ids = list(current_ids)
                    st.session_state.metadata_fetched = False
                    st.session_state.metadata = {}

        # --- Tab 3: Examples ---
        with tab_example:
            # Use EXAMPLES from examples.protein_sets
            example_names = ["Select an example..."] + list(EXAMPLES.keys())
            selected_example = st.selectbox("Choose a dataset:", example_names)

            if selected_example != "Select an example...":
                def load_example_callback(ex_name):
                    st.session_state.input_pdb_text_dashboard = ""
                    st.session_state.pdb_ids = EXAMPLES[ex_name]
                    st.session_state.metadata_fetched = False
                    st.session_state.metadata = {}
                    
                st.button(
                    f"Load {selected_example}", 
                    on_click=load_example_callback, 
                    args=(selected_example,)
                )
