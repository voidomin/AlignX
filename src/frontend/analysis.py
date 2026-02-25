import asyncio

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
    """
    progress_bar = st.progress(0)
    status_text = st.empty()

    # Progress callback for the coordinator
    def on_progress(fraction: float, message: str, step: int):
        render_progress_stepper(step)
        status_text.text(message)
        progress_bar.progress(fraction)

    try:
        # Prepare chain selection mapping
        chain_selection = {}

        # 1. Check for manual individual selections first
        manual_selections = st.session_state.get("manual_chain_selections", {})

        # 2. Apply logic based on mode
        mode = st.session_state.get("chain_selection_mode", "Auto (use first chain)")

        for pid in st.session_state.pdb_ids:
            # Individual selection takes precedence
            if pid in manual_selections:
                chain_selection[pid] = manual_selections[pid]
            elif mode == "Specify chain ID":
                chain_selection[pid] = st.session_state.get("selected_chain", "A")
            # Else: Coordinator will default to first chain (Auto)

        # Execute via coordinator
        success, msg, results = st.session_state.coordinator.run_full_pipeline(
            pdb_ids=st.session_state.pdb_ids,
            progress_callback=on_progress,
            chain_selection=chain_selection,
            remove_water=st.session_state.get("remove_water", True),
            remove_heteroatoms=st.session_state.get("remove_hetero", True),
        )

        if not success:
            st.error(f"Analysis Failed: {msg}")
            return

        # Update session state with results
        st.session_state.results = results

        # UI Polish
        progress_bar.progress(1.0)
        status_text.text("✅ Analysis complete!")
        st.success("Analysis completed successfully!")
        st.balloons()
        st.rerun()

    except Exception as e:
        st.error(f"Execution Error: {str(e)}")
        logger.error(f"Execution Error: {str(e)}", exc_info=True)


def render_dashboard() -> None:
    """
    Render the main Analysis Dashboard (Mission Control).

    Handles both the pre-analysis configuration (ID entry, upload)
    and the post-analysis result display.
    """

    # 1. Dashboard Header
    st.caption(
        "Perform rigorous structural alignment, RMSD calculations, and phylogenetic analysis."
    )

    results = st.session_state.get("results")
    pdb_ids = st.session_state.get("pdb_ids", [])

    # Top Inputs FIRST — always visible before analysis
    if not results:
        render_input_section(st.session_state.pdb_manager)
        st.divider()

    # Show Hero Dashboard toggle if nothing is selected yet
    if not results and not pdb_ids:
        from src.frontend import home

        if st.toggle("📊 Show Mission Control Dashboard", value=False):
            home.render_hero_section()

    # 2. Status & Metrics Bar
    st.divider()
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric("Proteins Loaded", len(st.session_state.pdb_ids))
    with col_m2:
        status = "Analysis Complete" if st.session_state.results else "Ready to Run"
        if not st.session_state.results and not st.session_state.pdb_ids:
            status = "Waiting for Input"
        st.metric("System Status", status)
    with col_m3:
        if st.session_state.results:
            try:
                df = st.session_state.results.get("rmsd_df")
                if df is not None:
                    # Calculate avg RMSD from upper triangle
                    import numpy as np

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
    with col_m4:
        if st.button("⏪ RESET MISSION", type="secondary", use_container_width=True):
            st.session_state.pdb_ids = []
            st.session_state.results = None
            st.session_state.metadata = {}
            st.session_state.metadata_fetched = False
            st.session_state.highlighted_residues = []
            st.session_state.highlight_protein = "All Proteins"
            st.session_state.residue_selections = {}
            st.session_state.highlight_chains = {}
            st.session_state.insights = None
            st.session_state.insights_run_id = None
            if "chain_info" in st.session_state:
                del st.session_state.chain_info

            # Explicit Deep Cache Bust
            st.cache_data.clear()
            st.rerun()

        if st.button(
            "🧹 DEEP CLEAN CACHE",
            type="secondary",
            use_container_width=True,
            help="Wipe your session's downloaded/cleaned PDB files and reset everything.",
        ):
            # 1. Delete THIS SESSION's structural files from disk
            session_id = st.session_state.get("session_id")
            if session_id:
                session_dirs = [
                    Path("data/raw") / session_id,
                    Path("data/cleaned") / session_id,
                ]
            else:
                # Fallback: legacy mode (no session isolation)
                session_dirs = [Path("data/raw"), Path("data/cleaned")]

            for data_dir in session_dirs:
                if data_dir.exists():
                    import shutil
                    shutil.rmtree(data_dir, ignore_errors=True)
                    logger.info(f"Deep clean: wiped {data_dir}")

            # 2. Clear ALL caches
            st.cache_data.clear()
            try:
                st.cache_resource.clear()
            except Exception as exc:
                logger.debug(f"Failed to clear resource cache: {exc}")

            # 3. Full session state reset
            st.session_state.pdb_ids = []
            st.session_state.results = None
            st.session_state.metadata = {}
            st.session_state.metadata_fetched = False
            st.session_state.highlighted_residues = []
            st.session_state.highlight_protein = "All Proteins"
            st.session_state.residue_selections = {}
            st.session_state.highlight_chains = {}
            st.session_state.insights = None
            st.session_state.insights_run_id = None
            if "chain_info" in st.session_state:
                del st.session_state.chain_info

            st.toast("🧹 Deep clean complete! All caches and files wiped.", icon="✅")
            st.rerun()

    # 3. Main Content Area
    # CASE A: Results Exist -> Show Results
    if results:
        display_results()

    # CASE B: No Results -> Show Pre-Analysis Tools
    elif st.session_state.pdb_ids:
        st.subheader(f"Selected: {len(st.session_state.pdb_ids)} Proteins")

        # Metadata Expander
        with st.expander("📋 Protein Metadata", expanded=True):
            if not st.session_state.metadata_fetched:
                with st.spinner("Fetching protein metadata..."):
                    try:
                        metadata = cached_fetch_metadata(
                            st.session_state.pdb_manager, st.session_state.pdb_ids
                        )
                        st.session_state.metadata = metadata
                        st.session_state.metadata_fetched = True
                    except Exception as e:
                        st.error(f"Metadata fetch failed: {str(e)}")
                        st.info(
                            "💡 Try clicking **🧹 DEEP CLEAN CACHE** in the top-right metrics bar to resolve this."
                        )

            render_metadata_viewer(st.session_state.pdb_ids, st.session_state.metadata)

        # Action Buttons
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button(
                "🔍 Analyze Chains",
                help="Check chain information before running alignment",
                use_container_width=True,
            ):
                with st.spinner("Analyzing structures..."):
                    download_results = cached_batch_download(
                        st.session_state.pdb_manager, st.session_state.pdb_ids
                    )
                    chain_info = {}
                    for pdb_id, (success, msg, path) in download_results.items():
                        if success and path:
                            try:
                                info = cached_analyze_structure(
                                    st.session_state.pdb_manager, path
                                )
                                chain_info[pdb_id] = info
                            except Exception as e:
                                st.error(f"Error analyzing {pdb_id}: {str(e)}")
                    st.session_state.chain_info = chain_info

        with col2:
            if st.button("▶️ Run Analysis", type="primary", use_container_width=True):
                run_analysis()

        # Chain Info Display
        if "chain_info" in st.session_state:
            render_chain_selector(st.session_state.chain_info)

    # 4. Console
    log_file = st.session_state.get("log_file")
    render_console(Path(log_file) if log_file else None)
