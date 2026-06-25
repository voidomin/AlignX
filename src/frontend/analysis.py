import asyncio
import time

import streamlit as st
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
from src.utils.logger import get_logger
from examples.protein_sets import EXAMPLES
from src.frontend.console import render_console
from src.frontend.results import display_results

# Backend Imports
from src.frontend.tabs.common import render_progress_stepper
from src.frontend.components.input_section import render_input_section
from src.frontend.components.metadata_viewer import render_metadata_viewer
from src.frontend.components.chain_selector import render_chain_selector

logger = get_logger()


# -----------------------------------------------------------------------------
# User-Friendly Error Translation  (#3)
# -----------------------------------------------------------------------------

def _friendly_error(msg: str) -> str:
    """Convert technical pipeline errors into user-friendly messages."""
    m = msg.lower()
    if "mustang" in m and ("command" in m or "not found" in m or "wsl" in m):
        return (
            "⚠️ **Mustang could not start.** Try clicking **New Analysis** to reset, "
            "then run again. If the issue persists, check the System Health panel in the sidebar."
        )
    if "download" in m or "rcsb" in m or "http" in m or "connection" in m:
        return (
            "🌐 **Download failed.** One or more PDB IDs could not be fetched from RCSB. "
            "Check that each ID is a valid 4-letter PDB code and you have internet access."
        )
    if "timeout" in m:
        return (
            "⏱️ **Alignment timed out.** Try using fewer structures (≤8) or pick a simpler "
            "example dataset. Large or highly diverse structures can take much longer."
        )
    if "chain" in m:
        return (
            "🔗 **Chain error.** One structure may have no usable chain. "
            "Try ‘Analyze Chains’ before running to inspect the structure manually."
        )
    if "alignment.pdb" in m or "did not produce" in m:
        return (
            "❌ **Mustang returned no output.** The structures may be too dissimilar to align, "
            "or a file was corrupted. Try with different PDB IDs."
        )
    return f"❌ **Pipeline error:** {msg}\n\n💡 Try resetting the session and running again."


# -----------------------------------------------------------------------------
# Get Started Card  (#1)
# -----------------------------------------------------------------------------

def _render_get_started_card() -> None:
    """Show a welcoming empty state with a clear 3-step CTA."""
    st.markdown(
        """
        <div style="
            margin: 2rem auto;
            max-width: 680px;
            background: linear-gradient(135deg, rgba(255,126,66,0.06) 0%, rgba(66,234,255,0.06) 100%);
            border: 1px solid rgba(255,126,66,0.25);
            border-radius: 16px;
            padding: 2.5rem 2rem;
            text-align: center;
        ">
            <div style="font-size:3rem; margin-bottom:0.5rem;">🧬</div>
            <h2 style="
                margin: 0 0 0.5rem;
                font-size: 1.6rem;
                background: linear-gradient(135deg, #fff 0%, #ff7e42 100%);
                -webkit-background-clip: text;
                background-clip: text;
                -webkit-text-fill-color: transparent;
            ">Protein Structural Alignment</h2>
            <p style="color:#c0c0c0; margin: 0 0 2rem; font-size:0.95rem;">
                Compare protein 3D structures, compute RMSD matrices,<br>
                and explore evolutionary relationships — in one click.
            </p>
            <div style="display:flex; gap:1rem; justify-content:center; flex-wrap:wrap; margin-bottom:1.5rem;">
                <div style="
                    background:rgba(255,126,66,0.1); border:1px solid rgba(255,126,66,0.3);
                    border-radius:10px; padding:0.8rem 1.2rem; min-width:140px;
                ">
                    <div style="font-size:1.5rem">ㆱ️</div>
                    <div style="color:#fff; font-weight:600; font-size:0.85rem; margin-top:4px">Search</div>
                    <div style="color:#888; font-size:0.75rem">Enter PDB IDs or load an example</div>
                </div>
                <div style="
                    background:rgba(66,234,255,0.07); border:1px solid rgba(66,234,255,0.2);
                    border-radius:10px; padding:0.8rem 1.2rem; min-width:140px;
                ">
                    <div style="font-size:1.5rem">ㆲ️</div>
                    <div style="color:#fff; font-weight:600; font-size:0.85rem; margin-top:4px">Review</div>
                    <div style="color:#888; font-size:0.75rem">Check protein metadata &amp; chains</div>
                </div>
                <div style="
                    background:rgba(66,114,255,0.07); border:1px solid rgba(66,114,255,0.2);
                    border-radius:10px; padding:0.8rem 1.2rem; min-width:140px;
                ">
                    <div style="font-size:1.5rem">ㆳ️</div>
                    <div style="color:#fff; font-weight:600; font-size:0.85rem; margin-top:4px">Align</div>
                    <div style="color:#888; font-size:0.75rem">Run Mustang &amp; explore results</div>
                </div>
            </div>
            <p style="color:#666; font-size:0.78rem; margin:0;">
                💡 Try the <strong style="color:#ff7e42">Load Example</strong> tab above for an instant demo
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_protein_pill_bar(pdb_ids: List[str]) -> None:
    """Render a slim horizontal bar of protein ID pills (#7)."""
    pill_html = '<div style="display:flex; flex-wrap:wrap; gap:6px; margin:0.5rem 0 1rem;">'
    for pid in pdb_ids:
        pill_html += (
            f'<span style="'
            f'background:rgba(66,234,255,0.1); border:1px solid rgba(66,234,255,0.3);'
            f'border-radius:20px; padding:3px 12px; font-size:0.82rem;'
            f'font-family:monospace; color:#42eaff;">'
            f'{pid}</span>'
        )
    pill_html += "</div>"
    st.markdown(pill_html, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Cached Wrappers
# -----------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def cached_batch_download(
    _pdb_manager: Any, pdb_ids: List[str]
) -> Dict[str, Tuple[bool, str, Optional[Path]]]:
    """
    Cached wrapper for batch PDB download.

    Args:
        _pdb_manager: The PDBManager instance (backend).
        pdb_ids: List of 4-character PDB identifiers.

    Returns:
        Dictionary mapping PDB IDs to (success, message, local_path) tuples.
    """
    return asyncio.run(_pdb_manager.batch_download(pdb_ids))


@st.cache_data(show_spinner=False)
def cached_analyze_structure(_pdb_manager: Any, file_path: Path) -> Dict[str, Any]:
    """
    Cached wrapper for structure analysis.

    Args:
        _pdb_manager: The PDBManager instance.
        file_path: Path to the PDB file.

    Returns:
        Dictionary containing chain and residue information.
    """
    return _pdb_manager.analyze_structure(file_path)


@st.cache_data(show_spinner=False)
def cached_fetch_metadata(
    _pdb_manager: Any, pdb_ids: List[str]
) -> Dict[str, Dict[str, str]]:
    """
    Cached wrapper for metadata fetching.

    Args:
        _pdb_manager: The PDBManager instance.
        pdb_ids: List of PDB IDs.

    Returns:
        Dictionary mapping IDs to metadata dictionaries (title, organism, etc).
    """
    return asyncio.run(_pdb_manager.fetch_metadata(pdb_ids))


# -----------------------------------------------------------------------------
# Analysis Logic
# -----------------------------------------------------------------------------


def load_run_from_history(run_id: str, is_auto: bool = False) -> None:
    """
    Load a past run from the database.

    Args:
        run_id: ID of the run to restore.
        is_auto: Whether this is an automatic recovery (silent).
    """
    run = st.session_state.history_db.get_run(run_id)
    if not run:
        if not is_auto:
            st.error("Run not found in database.")
        return

    result_path = Path(run["result_path"])
    if not result_path.exists():
        if not is_auto:
            st.error(f"Result directory not found: {result_path}")
        return

    # Set state
    st.session_state.pdb_ids = run["pdb_ids"]
    st.session_state.metadata = run.get("metadata", {})
    st.session_state.metadata_fetched = True if st.session_state.metadata else False

    # Sync widgets
    meta = run.get("metadata", {})
    input_method = meta.get("input_method", "Manual Entry")
    st.session_state.input_method_radio = input_method

    if input_method == "Manual Entry":
        st.session_state.manual_pdb_input = "\n".join(run["pdb_ids"])
    elif input_method == "Load Example":
        st.session_state.example_select = meta.get(
            "example_name", list(EXAMPLES.keys())[0]
        )

    # Load results via Coordinator
    if is_auto:
        # Silent recovery
        results = st.session_state.coordinator.process_result_directory(
            result_path, run["pdb_ids"]
        )
        if results:
            results["id"] = run["id"]
            results["name"] = run["name"]
            results["timestamp"] = run["timestamp"]
            st.session_state.results = results
    else:
        with st.spinner("Restoring analysis results..."):
            results = st.session_state.coordinator.process_result_directory(
                result_path, run["pdb_ids"]
            )
            if results:
                results["id"] = run["id"]
                results["name"] = run["name"]
                results["timestamp"] = run["timestamp"]
                st.session_state.results = results
                st.success(f"Loaded run: {run['name']}")
                st.rerun()
            else:
                st.error("Failed to process result directory.")


def run_analysis() -> None:
    """
    Run the complete analysis pipeline using the AnalysisCoordinator.
    Includes live elapsed-time counter and stage banners (#2).
    """
    n = len(st.session_state.pdb_ids)

    # Stage banner (#2)
    stage_banner = st.empty()
    stage_banner.info(f"⚙️ Starting alignment of **{n} structure{'s' if n != 1 else ''}**…")

    progress_bar = st.progress(0)
    status_text = st.empty()
    timer_display = st.empty()
    start_time = time.time()

    def on_progress(fraction: float, message: str, step: int):
        render_progress_stepper(step)
        elapsed = int(time.time() - start_time)
        mins, secs = divmod(elapsed, 60)
        timer_str = f"{mins}m {secs:02d}s" if mins else f"{secs}s"

        stage_labels = {
            1: f"📥 Downloading {n} structure files…",
            2: "🧹 Cleaning &amp; filtering PDB files…",
            3: f"⚙️ Running Mustang alignment on {n} structures… (this is the slow step)",
            4: "📊 Computing RMSD matrix &amp; generating charts…",
        }
        stage_banner.info(stage_labels.get(step, message))
        status_text.caption(message)
        progress_bar.progress(fraction)
        timer_display.caption(f"⏱ Elapsed: **{timer_str}**")

    try:
        # Prepare chain selection mapping
        chain_selection = {}
        manual_selections = st.session_state.get("manual_chain_selections", {})
        mode = st.session_state.get("chain_selection_mode", "Auto (use first chain)")

        for pid in st.session_state.pdb_ids:
            if pid in manual_selections:
                chain_selection[pid] = manual_selections[pid]
            elif mode == "Specify chain ID":
                chain_selection[pid] = st.session_state.get("selected_chain", "A")

        success, msg, results = st.session_state.coordinator.run_full_pipeline(
            pdb_ids=st.session_state.pdb_ids,
            progress_callback=on_progress,
            chain_selection=chain_selection,
            remove_water=st.session_state.get("remove_water", True),
            remove_heteroatoms=st.session_state.get("remove_hetero", True),
        )

        if not success:
            stage_banner.empty()
            timer_display.empty()
            st.error(_friendly_error(msg))
            return

        st.session_state.results = results
        elapsed = int(time.time() - start_time)
        mins, secs = divmod(elapsed, 60)
        timer_str = f"{mins}m {secs:02d}s" if mins else f"{secs}s"
        progress_bar.progress(1.0)
        stage_banner.success(f"✅ Alignment complete in **{timer_str}**!")
        status_text.empty()
        timer_display.empty()
        st.balloons()
        st.rerun()

    except Exception as e:
        stage_banner.empty()
        timer_display.empty()
        st.error(_friendly_error(str(e)))
        logger.error(f"Execution Error: {str(e)}", exc_info=True)


def render_dashboard() -> None:
    """
    Render the main Analysis Dashboard.
    Handles both pre-analysis configuration and post-analysis result display.
    """

    # First-run Guided Mode prompt (#10) — show once, dismissable
    if st.session_state.get("first_visit", True) and not st.session_state.get("guided_mode"):
        with st.container():
            st.markdown(
                """
                <div style="
                    background: rgba(255,126,66,0.08);
                    border: 1px solid rgba(255,126,66,0.3);
                    border-radius: 10px;
                    padding: 0.8rem 1.2rem;
                    margin-bottom: 0.8rem;
                    display: flex; align-items: center; gap: 1rem; flex-wrap: wrap;
                ">
                    <span style="font-size:1.4rem;">🎓</span>
                    <span style="flex:1; color:#e0c8b0; font-size:0.88rem;">
                        <strong>First time here?</strong> Enable <strong>Guided Mode</strong>
                        for explanations on every tab.
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
            gc1, gc2 = st.columns([2, 1])
            with gc1:
                if st.button("🎓 Enable Guided Mode", use_container_width=True):
                    st.session_state.guided_mode = True
                    st.session_state.first_visit = False
                    st.rerun()
            with gc2:
                if st.button("Dismiss", use_container_width=True):
                    st.session_state.first_visit = False
                    st.rerun()

    st.caption(
        "Perform rigorous structural alignment, RMSD calculations, and phylogenetic analysis."
    )

    results = st.session_state.get("results")
    pdb_ids = st.session_state.get("pdb_ids", [])

    # Always-visible input section when no results yet
    if not results:
        render_input_section(st.session_state.pdb_manager)
        st.divider()

    # Slim metrics row — 3 columns, no destructive buttons here (#4)
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric("Proteins Loaded", len(pdb_ids))
    with col_m2:
        status = "Analysis Complete" if results else "Ready to Run"
        if not results and not pdb_ids:
            status = "Waiting for Input"
        st.metric("System Status", status)
    with col_m3:
        if results:
            try:
                import numpy as np
                df = results.get("rmsd_df")
                if df is not None:
                    vals = df.values
                    upper_tri = vals[np.triu_indices_from(vals, k=1)]
                    avg_rmsd = np.mean(upper_tri) if len(upper_tri) > 0 else 0
                    st.metric("Global Avg RMSD", f"{avg_rmsd:.2f} Å")
                else:
                    st.metric("Alignment", "Done")
            except Exception:
                st.metric("Alignment", "Done")
        else:
            st.metric("Mode", "Analysis")

    # CASE A: Results Exist -> Show Results
    if results:
        display_results()

    # CASE B: IDs loaded, no results -> Show pre-analysis tools (#6, #7)
    elif pdb_ids:
        st.subheader(f"Selected: {len(pdb_ids)} Proteins")
        _render_protein_pill_bar(pdb_ids)

        # Lazy metadata (#7) — only show on demand
        col_a, col_b, col_c = st.columns([2, 1, 1])
        with col_a:
            if st.button(
                "▶️ Run Analysis",
                type="primary",
                use_container_width=True,
                help=f"Align {len(pdb_ids)} structures using Mustang",
            ):
                run_analysis()
        with col_b:
            label = "Hide Info" if st.session_state.get("show_metadata") else "📋 Show Protein Info"
            if st.button(label, use_container_width=True):
                st.session_state.show_metadata = not st.session_state.get("show_metadata", False)
                st.rerun()
        with col_c:
            if st.button(
                "🔍 Analyze Chains",
                help="Check chain information before running alignment",
                use_container_width=True,
            ):
                with st.spinner("Analyzing structures…"):
                    download_results = cached_batch_download(
                        st.session_state.pdb_manager, pdb_ids
                    )
                    chain_info = {}
                    for pdb_id, (ok, msg, path) in download_results.items():
                        if ok and path:
                            try:
                                info = cached_analyze_structure(
                                    st.session_state.pdb_manager, path
                                )
                                chain_info[pdb_id] = info
                            except Exception as e:
                                st.error(f"Error analyzing {pdb_id}: {str(e)}")
                    st.session_state.chain_info = chain_info

        # Lazy metadata expander (#7)
        if st.session_state.get("show_metadata", False):
            with st.expander("📋 Protein Metadata", expanded=True):
                if not st.session_state.metadata_fetched:
                    with st.spinner("Fetching protein metadata…"):
                        try:
                            metadata = cached_fetch_metadata(
                                st.session_state.pdb_manager, pdb_ids
                            )
                            st.session_state.metadata = metadata
                            st.session_state.metadata_fetched = True
                        except Exception as e:
                            st.error(f"Metadata fetch failed: {str(e)}")
                render_metadata_viewer(pdb_ids, st.session_state.metadata)

        if "chain_info" in st.session_state:
            render_chain_selector(st.session_state.chain_info)

    # CASE C: Nothing entered -> welcoming empty state (#1)
    else:
        _render_get_started_card()

    # Console
    log_file = st.session_state.get("log_file")
    render_console(Path(log_file) if log_file else None)

