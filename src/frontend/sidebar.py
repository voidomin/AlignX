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

    # Clear ZIP buffers cached in session state to prevent memory leakage.
    # list(...) is required here, not redundant - the loop body deletes
    # from st.session_state, which would raise "dictionary changed size
    # during iteration" without this defensive copy. SonarQube's S7504
    # flags this as an unnecessary list() call; it's a false positive that
    # doesn't see the mutation inside the loop body below - do not "fix".
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


def _render_mustang_status() -> None:
    mustang_ok, mustang_msg = st.session_state.mustang_install_status
    if mustang_ok:
        st.success(f"✓ {mustang_msg}")
    else:
        st.error(f"✗ {mustang_msg}")
        st.info("See docs/setup/WINDOWS_SETUP.md for installation instructions")


def _get_current_mem_mb() -> float:
    import os
    import psutil

    try:
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except Exception:
        return 0.0


def _render_free_ram_button(initial_mem: float) -> None:
    import os
    import gc
    import psutil

    if not st.button(
        "🧹 Free RAM",
        help="Force garbage collection and clear caching layers to free memory",
    ):
        return
    st.cache_data.clear()
    try:
        st.cache_resource.clear()
    except Exception:
        pass
    gc.collect()
    try:
        new_mem = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
        freed = initial_mem - new_mem
        if freed > 0.1:
            st.toast(f"Freed {freed:.1f} MB of RAM!", icon="🧹")
        else:
            st.toast("RAM is already fully optimized!", icon="✅")
    except Exception:
        st.toast("Memory cleanup complete!", icon="✅")
    st.rerun()


def _render_clear_logs_button() -> None:
    if st.button(
        "🧹 Clear Logs", type="secondary", help="Delete temporary run directories"
    ):
        st.session_state.system_manager.cleanup_old_runs(days=0)
        st.success("Temp files cleared.")


def _render_ram_health_row(current_mem: float) -> None:
    if current_mem > 0.0:
        st.metric(
            label="Live Server RAM Usage",
            value=f"{current_mem:.1f} MB",
            help="Current RAM (RSS) consumed by the Streamlit application process.",
        )

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        _render_free_ram_button(current_mem)
    with col_g2:
        _render_clear_logs_button()


def _render_package_status_row() -> None:
    import sys

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


def _render_diagnostics_results(res: dict) -> None:
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


def _render_diagnostics_section() -> None:
    if st.button("🔍 Run Diagnostics"):
        with st.spinner("Checking dependencies..."):
            executable = getattr(
                st.session_state.get("mustang_runner"), "executable", "mustang"
            )
            st.session_state.diag_results = (
                st.session_state.system_manager.run_diagnostics(
                    mustang_executable=executable
                )
            )

    if "diag_results" in st.session_state:
        _render_diagnostics_results(st.session_state.diag_results)


def _render_system_health_expander() -> None:
    with st.expander("🛠️ System Health", expanded=False):
        current_mem = _get_current_mem_mb()
        _render_ram_health_row(current_mem)
        _render_package_status_row()
        st.divider()
        _render_diagnostics_section()


def _render_soft_reset_controls() -> None:
    if not st.session_state.get("_confirm_reset"):
        if st.button(
            "🔄 New Analysis",
            help="Clear current results and start fresh (keeps downloaded files)",
        ):
            st.session_state._confirm_reset = True
            st.rerun()
        return

    st.warning("This will clear your current results. Are you sure?")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Confirm", type="primary"):
            _do_soft_reset()
            st.session_state._confirm_reset = False
            st.rerun()
    with c2:
        if st.button("❌ Cancel"):
            st.session_state._confirm_reset = False
            st.rerun()


def _render_deep_clean_controls() -> None:
    if not st.session_state.get("_confirm_deep_clean"):
        if st.button(
            "🧹 Clear All Files",
            type="secondary",
            help="Delete all downloaded/cleaned PDB files and reset everything",
        ):
            st.session_state._confirm_deep_clean = True
            st.rerun()
        return

    st.error("⚠️ This will delete all downloaded PDB files and reset everything.")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✅ Delete Files", type="primary"):
            with st.spinner("Wiping session data..."):
                _do_deep_clean()
            st.session_state._confirm_deep_clean = False
            st.toast("🧹 All files wiped!", icon="✅")
            st.rerun()
    with c2:
        if st.button("❌ Cancel", key="cancel_deep"):
            st.session_state._confirm_deep_clean = False
            st.rerun()


def _render_session_controls_expander() -> None:
    with st.expander("🗑️ Session", expanded=False):
        st.caption("Use these to start over or free up disk space.")
        _render_soft_reset_controls()
        _render_deep_clean_controls()


def _get_history_runs() -> list:
    try:
        session_id = st.session_state.get("session_id")
        return st.session_state.history_db.get_all_runs(limit=6, session_id=session_id)
    except TypeError:
        return st.session_state.history_db.get_all_runs()[:6]


def _render_history_run_card(
    run: dict, load_run_callback: Callable[[str], None]
) -> None:
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
            "📂 Load", key=f"load_{run['id']}", help=f"Restore: {run['name']}"
        ):
            load_run_callback(run["id"])
    with col2:
        if st.button("🗑️", key=f"del_{run['id']}", help="Delete this run"):
            st.session_state.history_db.delete_run(run["id"])
            st.rerun()


def _render_history_expander(load_run_callback: Callable[[str], None]) -> None:
    with st.expander("📜 History", expanded=False):
        runs = _get_history_runs()

        if not runs:
            st.info("No saved runs yet. Run an analysis to see it here.")
            return

        for run in runs:
            _render_history_run_card(run, load_run_callback)

        if len(runs) > 1 and st.button("🗑️ Clear All History", type="secondary"):
            for run in runs:
                st.session_state.history_db.delete_run(run["id"])
            st.rerun()


def _is_multi_chain_detected() -> bool:
    chain_info = st.session_state.get("chain_info", {})
    return any(
        len(info.get("chains", [])) > 1
        for info in chain_info.values()
        if isinstance(info, dict)
    )


def _render_chain_selection_controls() -> None:
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


def _render_structure_options_expander() -> None:
    """Structure Options (renamed from 'Advanced Options') (#11)."""
    multi_chain_detected = _is_multi_chain_detected()
    opts_label = "🔬 Structure Options" + (" ⚠️" if multi_chain_detected else "")

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
        _render_chain_selection_controls()


def render_sidebar(load_run_callback: Callable[[str], None]) -> None:
    """
    Render the sidebar configuration and history.

    Args:
        load_run_callback: Function to call when loading a run from history.
                           Takes a run_id (str) as argument.
    """
    with st.sidebar:
        st.header("⚙️ Setup")
        _render_mustang_status()

        _render_system_health_expander()
        st.divider()

        _render_session_controls_expander()
        st.divider()

        _render_history_expander(load_run_callback)
        st.divider()

        # --- Guided Mode Toggle (#10) ---
        st.session_state.guided_mode = st.toggle(
            "🎓 Guided Mode",
            value=st.session_state.guided_mode,
            help="Enable interactive explanations for each result tab.",
        )

        _render_structure_options_expander()

        version = st.session_state.config.get("app", {}).get("version", "?.?.?")
        st.caption(f"🧬 **AlignX** `v{version}`")
