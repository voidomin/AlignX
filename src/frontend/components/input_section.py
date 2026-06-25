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
                placeholder="e.g., 1LYZ, 2LYZ, 3LYZ",
                help="Supports 4-letter PDB codes or AlphaFold identifiers. Comma-separated.",
                key="input_pdb_text_dashboard",
                on_change=on_pdb_input_change,
            )

            # Inline validation badges (#5)
            if pdb_input:
                import re
                raw_ids = [pid.strip() for pid in pdb_input.split(",") if pid.strip()]
                badges_html = '<div style="display:flex; flex-wrap:wrap; gap:6px; margin:4px 0 8px;">'
                all_valid = True
                for pid in raw_ids:
                    p = pid.strip()
                    if p.upper().startswith("AF-"):
                        color, border, text = "rgba(66,114,255,0.15)", "rgba(66,114,255,0.5)", "#7eaaff"
                        icon = "✨"
                        tip = "AlphaFold ID"
                    elif re.fullmatch(r"[A-Za-z0-9]{4}", p):
                        color, border, text = "rgba(0,200,100,0.12)", "rgba(0,200,100,0.4)", "#00c864"
                        icon = "✓"
                        tip = "Valid PDB"
                    else:
                        color, border, text = "rgba(255,80,80,0.12)", "rgba(255,80,80,0.4)", "#ff6060"
                        icon = "✗"
                        tip = "Invalid — must be 4 characters"
                        all_valid = False
                    badges_html += (
                        f'<span title="{tip}" style="'
                        f'background:{color}; border:1px solid {border};'
                        f'border-radius:20px; padding:2px 10px; font-size:0.8rem;'
                        f'font-family:monospace; color:{text}; cursor:default;'
                        f'">{icon} {p.upper()}</span>'
                    )
                badges_html += "</div>"
                if not all_valid:
                    badges_html += '<p style="color:#ff8080; font-size:0.75rem; margin:0;">'
                    badges_html += '⚠️ Some IDs look invalid. PDB codes must be exactly 4 alphanumeric characters.</p>'
                st.markdown(badges_html, unsafe_allow_html=True)

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
