import streamlit as st
from typing import Any, List
from examples.protein_sets import EXAMPLES
import urllib.request
import urllib.parse
import json
import re


@st.cache_data(ttl=600, show_spinner=False, max_entries=50)
def cached_rcsb_suggestions(query_text: str) -> List[str]:
    """Fetch matching PDB IDs from RCSB Suggest API."""
    if not query_text or len(query_text) < 1:
        return []

    q = {"type": "basic", "suggest": {"text": query_text, "size": 6}}
    try:
        url = f"https://search.rcsb.org/rcsbsearch/v2/suggest?json={urllib.parse.quote(json.dumps(q))}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3) as res:
            data = json.loads(res.read().decode())
            suggestions = data.get("suggestions", {})
            pdb_entries = suggestions.get(
                "rcsb_entry_container_identifiers.entry_id", []
            )

            results = []
            for entry in pdb_entries:
                raw_text = entry.get("text", "")
                clean_text = re.sub(r"<[^>]+>", "", raw_text).upper()
                if clean_text and len(clean_text) == 4 and clean_text not in results:
                    results.append(clean_text)
            return results
    except Exception:
        return []


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
                    raw_ids = [
                        pid.strip() for pid in pdb_input.split(",") if pid.strip()
                    ]
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
                        st.session_state.chain_info = {}
                        st.session_state.manual_chain_selections = {}

            pdb_input = st.text_input(
                "Enter IDs (PDB or AlphaFold)",
                placeholder="e.g., 1LYZ, 2LYZ, 3LYZ",
                help="Supports 4-letter PDB codes or AlphaFold identifiers. Comma-separated.",
                key="input_pdb_text_dashboard",
                on_change=on_pdb_input_change,
            )

            # Suggestions autocomplete pills
            last_item = ""
            current_input = st.session_state.get("input_pdb_text_dashboard", "")
            if current_input:
                parts = [p.strip() for p in current_input.split(",")]
                if parts:
                    last_item = parts[-1]

            if (
                last_item
                and 1 <= len(last_item) < 4
                and not last_item.upper().startswith("AF-")
            ):
                sugs = cached_rcsb_suggestions(last_item)
                existing_parts = [p.upper() for p in parts[:-1]]
                sugs = [s for s in sugs if s not in existing_parts]

                if sugs:
                    st.markdown(
                        "<div style='font-size:0.82rem; color:#ff7e42; font-weight:600; margin:0.3rem 0 0.1rem;'>💡 Suggested PDB IDs:</div>",
                        unsafe_allow_html=True,
                    )
                    cols = st.columns(len(sugs) if len(sugs) <= 6 else 6)
                    for idx, sug in enumerate(sugs[:6]):
                        with cols[idx]:

                            def make_select_callback(s=sug, p_list=list(parts)):
                                def select_suggestion():
                                    p_list[-1] = s
                                    new_val = ", ".join(p_list) + ", "
                                    st.session_state.input_pdb_text_dashboard = new_val

                                    raw_ids = [
                                        pid.strip()
                                        for pid in new_val.split(",")
                                        if pid.strip()
                                    ]
                                    clean_ids = []
                                    for pid in raw_ids:
                                        if pid.upper().startswith("AF-"):
                                            clean_ids.append(pid)
                                        else:
                                            clean_ids.append(pid.upper())

                                    st.session_state.pdb_ids = clean_ids
                                    st.session_state.metadata_fetched = False
                                    st.session_state.metadata = {}
                                    st.session_state.chain_info = {}
                                    st.session_state.manual_chain_selections = {}

                                return select_suggestion

                            st.button(
                                sug,
                                key=f"sug_{sug}_{idx}",
                                on_click=make_select_callback(sug, parts),
                                use_container_width=True,
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
                        color, border, text = (
                            "rgba(66,114,255,0.15)",
                            "rgba(66,114,255,0.5)",
                            "#7eaaff",
                        )
                        icon = "✨"
                        tip = "AlphaFold ID"
                    elif re.fullmatch(r"[A-Za-z0-9]{4}", p):
                        color, border, text = (
                            "rgba(0,200,100,0.12)",
                            "rgba(0,200,100,0.4)",
                            "#00c864",
                        )
                        icon = "✓"
                        tip = "Valid PDB"
                    else:
                        color, border, text = (
                            "rgba(255,80,80,0.12)",
                            "rgba(255,80,80,0.4)",
                            "#ff6060",
                        )
                        icon = "✗"
                        tip = "Invalid — must be 4 characters"
                        all_valid = False
                    badges_html += (
                        f'<span title="{tip}" style="'
                        f"background:{color}; border:1px solid {border};"
                        f"border-radius:20px; padding:2px 10px; font-size:0.8rem;"
                        f"font-family:monospace; color:{text}; cursor:default;"
                        f'">{icon} {p.upper()}</span>'
                    )
                badges_html += "</div>"
                if not all_valid:
                    badges_html += (
                        '<p style="color:#ff8080; font-size:0.75rem; margin:0;">'
                    )
                    badges_html += "⚠️ Some IDs look invalid. PDB codes must be exactly 4 alphanumeric characters.</p>"
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
                    st.session_state.chain_info = {}
                    st.session_state.manual_chain_selections = {}

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
                    st.session_state.chain_info = {}
                    st.session_state.manual_chain_selections = {}

                st.button(
                    f"Load {selected_example}",
                    on_click=load_example_callback,
                    args=(selected_example,),
                )
