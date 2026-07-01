import shutil
import streamlit as st
from pathlib import Path
from typing import Callable

# ---------------------------------------------------------------------------
# Helper: reset session (#4)
# ---------------------------------------------------------------------------


def _do_soft_reset():
    """Clear results and IDs but keep downloaded files."""
    import gc

    # Clear ZIP buffers cached in session state to prevent memory leakage
    for k in list(st.session_state.keys()):
        if k.startswith("zip_buffer_"):
            del st.session_state[k]

    for key in [
        "pdb_ids",
        "results",
        "metadata",
        "highlighted_residues",
        "residue_selections",
        "highlight_chains",
        "insights",
        "insights_run_id",
    ]:
        if key in ["pdb_ids"]:
            st.session_state[key] = []
        elif key in ["metadata", "residue_selections", "highlight_chains"]:
            st.session_state[key] = {}
        else:
            st.session_state[key] = None
    st.session_state.metadata_fetched = False
    st.session_state.highlight_protein = "All Proteins"
    st.session_state.show_metadata = False
    for k in ["chain_info"]:
        if k in st.session_state:
            del st.session_state[k]
    st.cache_data.clear()
    gc.collect()


def _do_deep_clean():
    """Delete session files from disk and fully reset state."""
    session_id = st.session_state.get("session_id")
    session_dirs = (
        [Path("data/raw") / session_id, Path("data/cleaned") / session_id]
        if session_id
        else [Path("data/raw"), Path("data/cleaned")]
    )
    for d in session_dirs:
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
    st.cache_data.clear()
    try:
        st.cache_resource.clear()
    except Exception:
        pass
    _do_soft_reset()
    import gc

    gc.collect()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


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
            st.info("See docs/setup/WINDOWS_SETUP.md for installation instructions")

        # --- System Health & Diagnostics ---
        with st.expander("🛠️ System Health", expanded=False):
            import os
            import sys
            import gc
            import psutil

            # Live RAM Usage
            try:
                process = psutil.Process(os.getpid())
                current_mem = process.memory_info().rss / (1024 * 1024)
            except Exception:
                current_mem = 0.0

            if current_mem > 0.0:
                st.metric(
                    label="Live Server RAM Usage",
                    value=f"{current_mem:.1f} MB",
                    help="Current RAM (RSS) consumed by the Streamlit application process.",
                )

            col_g1, col_g2 = st.columns(2)
            with col_g1:
                if st.button(
                    "🧹 Free RAM",
                    help="Force garbage collection and clear caching layers to free memory",
                ):
                    initial_mem = current_mem
                    st.cache_data.clear()
                    try:
                        st.cache_resource.clear()
                    except Exception:
                        pass
                    gc.collect()
                    try:
                        new_mem = process.memory_info().rss / (1024 * 1024)
                        freed = initial_mem - new_mem
                        if freed > 0.1:
                            st.toast(f"Freed {freed:.1f} MB of RAM!", icon="🧹")
                        else:
                            st.toast("RAM is already fully optimized!", icon="✅")
                    except Exception:
                        st.toast("Memory cleanup complete!", icon="✅")
                    st.rerun()

            with col_g2:
                if st.button(
                    "🧹 Clear Logs",
                    type="secondary",
                    help="Delete temporary run directories",
                ):
                    st.session_state.system_manager.cleanup_old_runs(days=0)
                    st.success("Temp files cleared.")

            st.write("**Loaded Heavy Packages**")
            packages = {
                "Bio": "Bio",
                "Matplotlib": "matplotlib",
                "Seaborn": "seaborn",
                "Plotly": "plotly",
                "SciPy": "scipy",
            }
            cols_pkg = st.columns(len(packages))
            for idx, (name, module_name) in enumerate(packages.items()):
                loaded = module_name in sys.modules
                with cols_pkg[idx]:
                    if loaded:
                        st.markdown(
                            f"<span style='color:#FF4B4B; font-weight:bold; font-size:0.75rem;' title='Loaded (consuming RAM)'>● {name}</span>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f"<span style='color:#666666; font-size:0.75rem;' title='Not loaded (optimized)'>○ {name}</span>",
                            unsafe_allow_html=True,
                        )

            st.divider()

            if st.button(
                "🔍 Run Diagnostics",
            ):
                with st.spinner("Checking dependencies..."):
                    executable = getattr(
                        st.session_state.get("mustang_runner"), "executable", "mustang"
                    )
                    results = st.session_state.system_manager.run_diagnostics(
                        mustang_executable=executable
                    )
                    st.session_state.diag_results = results

            if "diag_results" in st.session_state:
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

        st.divider()

        # --- Session Controls (#4) ---
        with st.expander("🗑️ Session", expanded=False):
            st.caption("Use these to start over or free up disk space.")

            # Soft reset with confirmation
            if st.session_state.get("_confirm_reset"):
                st.warning("This will clear your current results. Are you sure?")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button(
                        "✅ Confirm",
                        type="primary",
                    ):
                        _do_soft_reset()
                        st.session_state._confirm_reset = False
                        st.rerun()
                with c2:
                    if st.button(
                        "❌ Cancel",
                    ):
                        st.session_state._confirm_reset = False
                        st.rerun()
            else:
                if st.button(
                    "🔄 New Analysis",
                    help="Clear current results and start fresh (keeps downloaded files)",
                ):
                    st.session_state._confirm_reset = True
                    st.rerun()

            # Deep clean with confirmation
            if st.session_state.get("_confirm_deep_clean"):
                st.error(
                    "⚠️ This will delete all downloaded PDB files and reset everything."
                )
                c1, c2 = st.columns(2)
                with c1:
                    if st.button(
                        "✅ Delete Files",
                        type="primary",
                    ):
                        with st.spinner("Wiping session data..."):
                            _do_deep_clean()
                        st.session_state._confirm_deep_clean = False
                        st.toast("🧹 All files wiped!", icon="✅")
                        st.rerun()
                with c2:
                    if st.button(
                        "❌ Cancel",
                        key="cancel_deep",
                    ):
                        st.session_state._confirm_deep_clean = False
                        st.rerun()
            else:
                if st.button(
                    "🧹 Clear All Files",
                    type="secondary",
                    help="Delete all downloaded/cleaned PDB files and reset everything",
                ):
                    st.session_state._confirm_deep_clean = True
                    st.rerun()

        st.divider()

        # --- History (#9) - Clickable cards ---
        with st.expander("📜 History", expanded=False):
            try:
                session_id = st.session_state.get("session_id")
                runs = st.session_state.history_db.get_all_runs(
                    limit=6, session_id=session_id
                )
            except TypeError:
                runs = st.session_state.history_db.get_all_runs()[:6]

            if not runs:
                st.info("No saved runs yet. Run an analysis to see it here.")
            else:
                for run in runs:
                    # Build protein preview string
                    proteins = run.get("pdb_ids", [])
                    n = len(proteins)
                    preview = ", ".join(proteins[:3])
                    if n > 3:
                        preview += f" +{n - 3} more"
                    ts = run.get("timestamp", "")[:10]  # date only

                    st.markdown(
                        f"""
                        <div style="
                            background:rgba(255,255,255,0.04);
                            border:1px solid rgba(255,255,255,0.08);
                            border-radius:8px;
                            padding:0.6rem 0.8rem;
                            margin-bottom:0.5rem;
                        ">
                            <div style="font-weight:600; font-size:0.82rem; color:#fff; margin-bottom:2px;">
                                {run['name']}
                            </div>
                            <div style="font-family:monospace; font-size:0.75rem; color:#42eaff; margin-bottom:4px;">
                                {preview}
                            </div>
                            <div style="font-size:0.72rem; color:#666;">
                                {n} structure{'s' if n != 1 else ''} • {ts}
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        if st.button(
                            "📂 Load",
                            key=f"load_{run['id']}",
                            help=f"Restore: {run['name']}",
                        ):
                            load_run_callback(run["id"])
                    with col2:
                        if st.button(
                            "🗑️",
                            key=f"del_{run['id']}",
                            help="Delete this run",
                        ):
                            st.session_state.history_db.delete_run(run["id"])
                            st.rerun()

                if len(runs) > 1:
                    if st.button("🗑️ Clear All History", type="secondary"):
                        for run in runs:
                            st.session_state.history_db.delete_run(run["id"])
                        st.rerun()

        st.divider()

        # --- Guided Mode Toggle (#10) ---
        st.session_state.guided_mode = st.toggle(
            "🎓 Guided Mode",
            value=st.session_state.guided_mode,
            help="Enable interactive explanations for each result tab.",
        )

        # --- Structure Options (renamed from 'Advanced Options') (#11) ---
        # Auto-detect multi-chain hint
        chain_info = st.session_state.get("chain_info", {})
        multi_chain_detected = any(
            len(info.get("chains", [])) > 1
            for info in chain_info.values()
            if isinstance(info, dict)
        )
        opts_label = "🔬 Structure Options"
        if multi_chain_detected:
            opts_label += " ⚠️"

        with st.expander(opts_label, expanded=multi_chain_detected):
            if multi_chain_detected:
                st.caption(
                    "⚠️ Multi-chain structures detected — review chain selection below."
                )

            st.checkbox(
                "Filter large files",
                value=True,
                help="Automatically suggest chain extraction for large PDB files",
            )
            st.session_state.remove_water = st.checkbox(
                "Remove water molecules", value=st.session_state.remove_water
            )
            st.session_state.remove_hetero = st.checkbox(
                "Remove heteroatoms", value=st.session_state.remove_hetero
            )

            st.markdown("**Chain Selection**")
            chain_selection = st.radio(
                "How to handle multi-chain structures?",
                ["Auto (use first chain)", "Specify chain ID"],
                help="GPCRs and other proteins may have multiple chains. Choose how to handle them.",
                index=(
                    0
                    if st.session_state.chain_selection_mode == "Auto (use first chain)"
                    else 1
                ),
            )
            selected_chain = st.session_state.selected_chain
            if chain_selection == "Specify chain ID":
                selected_chain = (
                    st.text_input(
                        "Chain ID",
                        value=st.session_state.selected_chain,
                        max_chars=1,
                        help="Enter chain identifier (e.g., A, B, C)",
                    )
                    .strip()
                    .upper()
                )
            st.session_state.chain_selection_mode = chain_selection
            st.session_state.selected_chain = selected_chain

        # Version badge
        version = st.session_state.config.get("app", {}).get("version", "?.?.?")
        st.caption(f"🧬 **AlignX** `v{version}`")
