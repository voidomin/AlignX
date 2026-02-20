import streamlit as st
import pandas as pd
import numpy as np
import shutil
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
from src.utils.logger import get_logger
from datetime import datetime
from examples.protein_sets import EXAMPLES
from src.frontend.console import render_console
from src.frontend.results import display_results

# Backend Imports
from src.backend.pdb_manager import PDBManager
from src.backend.mustang_runner import MustangRunner
from src.backend.rmsd_analyzer import RMSDAnalyzer
from src.backend.database import HistoryDatabase
from src.backend.phylo_tree import PhyloTreeGenerator
from src.backend.report_generator import ReportGenerator
from src.backend.notebook_exporter import NotebookExporter

logger = get_logger()

# -----------------------------------------------------------------------------
# Cached Wrappers
# -----------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def cached_batch_download(_pdb_manager: Any, pdb_ids: List[str]) -> Dict[str, Tuple[bool, str, Optional[Path]]]:
    """
    Cached wrapper for batch PDB download.
    
    Args:
        _pdb_manager: The PDBManager instance (backend).
        pdb_ids: List of 4-character PDB identifiers.
        
    Returns:
        Dictionary mapping PDB IDs to (success, message, local_path) tuples.
    """
    return _pdb_manager.batch_download(pdb_ids, max_workers=4)

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
def cached_run_alignment(_mustang_runner: Any, pdb_files: List[Path], run_dir: Path) -> Tuple[bool, str, Optional[Path]]:
    """
    Cached wrapper for Mustang alignment.
    
    Args:
        _mustang_runner: The MustangRunner instance.
        pdb_files: List of paths to cleaned PDB files.
        run_dir: Directory where alignment output will be stored.
        
    Returns:
        Tuple of (success, message, result_directory).
    """
    return _mustang_runner.run_alignment(pdb_files, run_dir)

@st.cache_data(show_spinner=False)
def cached_fetch_metadata(_pdb_manager: Any, pdb_ids: List[str]) -> Dict[str, Dict[str, str]]:
    """
    Cached wrapper for metadata fetching.
    
    Args:
        _pdb_manager: The PDBManager instance.
        pdb_ids: List of PDB IDs.
        
    Returns:
        Dictionary mapping IDs to metadata dictionaries (title, organism, etc).
    """
    return _pdb_manager.fetch_metadata(pdb_ids)


# -----------------------------------------------------------------------------
# Analysis Logic
# -----------------------------------------------------------------------------

def process_result_directory(result_dir: Path, pdb_ids: List[str], run_id: str = "latest", timestamp: Optional[str] = None, name: str = "Latest Run") -> Tuple[bool, str]:
    """
    Process a Mustang result directory and generate all analysis artifacts.
    Re-uses existing logic to populate st.session_state.results.
    
    Args:
        result_dir: Path to the directory containing Mustang output files.
        pdb_ids: List of PDB IDs that were aligned.
        run_id: Unique identifier for this analysis run.
        timestamp: When the run was executed.
        name: Human-readable name for the run.
        
    Returns:
        Tuple of (success, message).
    """
    try:
        # Parse RMSD matrix
        rmsd_df = st.session_state.mustang_runner.parse_rmsd_matrix(
            result_dir,
            pdb_ids
        )
        
        if rmsd_df is None:
            return False, "Could not parse RMSD matrix"

        # Generate heatmap
        heatmap_path = result_dir / 'rmsd_heatmap.png'
        # We re-generate it to ensure it exists, or just use it if it does?
        # Re-generating is safer in case of cleanups
        st.session_state.rmsd_analyzer.generate_heatmap(rmsd_df, heatmap_path)
        
        # Calculate statistics
        stats = st.session_state.rmsd_analyzer.calculate_statistics(rmsd_df)

        # Get alignment PDB path for 3D visualization
        alignment_pdb = result_dir / 'alignment.pdb'
        alignment_afasta = result_dir / 'alignment.afasta'

        # Calculate Alignment Stats
        if alignment_afasta.exists():
            try:
                # We need sequence_viewer in session state, usually init in app.py
                if 'sequence_viewer' in st.session_state:
                    sequences = st.session_state.sequence_viewer.parse_afasta(alignment_afasta)
                    if sequences:
                        stats['chain_length'] = len(list(sequences.values())[0])
                        stats['seq_identity'] = st.session_state.sequence_viewer.calculate_identity(sequences)
            except Exception as e:
                logger.warning(f"Failed to calculate detailed stats: {e}")
        
        # Identify clusters
        clusters = st.session_state.rmsd_analyzer.identify_clusters(rmsd_df)
        
        # Generate phylogenetic tree
        tree_path = result_dir / 'phylogenetic_tree.png'
        newick_path = result_dir / 'tree.newick'
        
        phylo_generator = PhyloTreeGenerator(st.session_state.config)
        phylo_generator.generate_tree(rmsd_df, tree_path)
        phylo_generator.export_newick(rmsd_df, newick_path)
        
        # Generate Interactive Plotly Figures
        heatmap_fig = st.session_state.rmsd_analyzer.generate_plotly_heatmap(rmsd_df)
        tree_fig = phylo_generator.generate_plotly_tree(rmsd_df)
        
        # Get alignment PDB path for 3D visualization
        alignment_pdb = result_dir / 'alignment.pdb'
        alignment_afasta = result_dir / 'alignment.afasta'
        
        # Calculate Residue RMSF
        logger.info("Calculating Residue RMSF...")
        try:
            rmsf_values, conservation_labels = st.session_state.rmsd_analyzer.calculate_residue_rmsf(
                alignment_pdb, 
                alignment_afasta
            )
            logger.info(f"RMSF calculated: {len(rmsf_values)} residues")
        except Exception as e:
            logger.warning(f"RMSF calculation failed (continuing without it): {e}")
            rmsf_values = []
        
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Store results
        logger.info("Storing results in session state...")
        st.session_state.results = {
            'id': run_id,
            'timestamp': timestamp,
            'name': name,
            'pdb_ids': pdb_ids,
            'rmsd_df': rmsd_df,
            'heatmap_path': heatmap_path,
            'stats': stats,
            'clusters': clusters,
            'result_dir': result_dir,
            'tree_path': tree_path,
            'newick_path': newick_path,
            'heatmap_fig': heatmap_fig,
            'tree_fig': tree_fig,
            'alignment_pdb': alignment_pdb,
            'alignment_afasta': alignment_afasta,
            'rmsf_values': rmsf_values
        }
        
        # Clear cached insights so they regenerate
        if 'insights' in st.session_state:
            del st.session_state.insights
            
        logger.info("Results stored successfully.")
        return True, "Success"
    except Exception as e:
        logger.error(f"Error processing results: {e}", exc_info=True)
        return False, str(e)


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

    result_path = Path(run['result_path'])
    if not result_path.exists():
        if not is_auto:
            st.error(f"Result directory not found: {result_path}")
        return

    # Set state
    st.session_state.pdb_ids = run['pdb_ids']
    st.session_state.metadata = run.get('metadata', {})
    st.session_state.metadata_fetched = True if st.session_state.metadata else False
    
    # Sync widgets
    meta = run.get('metadata', {})
    input_method = meta.get('input_method', 'Manual Entry')
    st.session_state.input_method_radio = input_method
    
    if input_method == "Manual Entry":
        st.session_state.manual_pdb_input = "\n".join(run['pdb_ids'])
    elif input_method == "Load Example":
        st.session_state.example_select = meta.get('example_name', list(EXAMPLES.keys())[0])

    # Load results
    if is_auto:
        # Don't show spinner/success during auto-load to avoid UI jitter
        process_result_directory(result_path, run['pdb_ids'], run_id=run['id'], timestamp=run['timestamp'], name=run['name'])
    else:
        with st.spinner("Restoring analysis results..."):
            success, msg = process_result_directory(result_path, run['pdb_ids'])
            if success:
                st.success(f"Loaded run: {run['name']}")
                st.rerun()
            else:
                st.error(f"Failed to load run: {msg}")


def run_analysis() -> None:
    """
    Run the complete analysis pipeline.
    
    This function orchestrates:
    1. Downloading PDBs
    2. Cleaning/Filtering PDBs
    3. Structural Alignment (Mustang)
    4. Post-alignment Analysis (RMSD, Trees, RMSF)
    5. Saving to history
    """
    progress_bar = st.progress(0)
    status_text = st.empty()
    cancel_container = st.empty()
    
    # Initialize cancellation state
    if 'cancel_analysis' not in st.session_state:
        st.session_state.cancel_analysis = False
    
    def check_cancel(step_id):
        if cancel_container.button("🛑 Cancel Analysis", key=f"btn_cancel_{step_id}", use_container_width=True):
            st.session_state.cancel_analysis = True
            st.warning("Cancellation requested...")
        
        if st.session_state.cancel_analysis:
            st.session_state.cancel_analysis = False # Reset for next run
            st.error("Analysis cancelled by user.")
            progress_bar.empty()
            status_text.empty()
            cancel_container.empty()
            st.stop()
    
    try:
        # Step 1: Download PDB files
        check_cancel("download")
        status_text.text("📥 Step 1/4: Downloading PDB files...")
        progress_bar.progress(0.1)
        
        # Use CACHED download
        download_results = cached_batch_download(
            st.session_state.pdb_manager,
            st.session_state.pdb_ids
        )
        
        # Check for failures
        failed = [pid for pid, (success, msg, path) in download_results.items() if not success]
        if failed:
            st.error(f"Failed to download: {', '.join(failed)}")
            return
        
        pdb_files = [path for success, msg, path in download_results.values() if path]
        progress_bar.progress(0.3)
        
        check_cancel("clean")
        # Step 2: Clean PDB files
        status_text.text("🧹 Step 2/4: Cleaning PDB files...")
        
        cleaned_files = []
        for pdb_file in pdb_files:
            # Analyze structure to check for multiple chains
            try:
                # Use CACHED analysis
                structure_info = cached_analyze_structure(st.session_state.pdb_manager, pdb_file)
                
                # Determine which chain to use based on user preference
                chain_to_use = None
                if len(structure_info['chains']) > 1:
                    # Check user's chain selection preference
                    if st.session_state.get('chain_selection_mode') == "Specify chain ID":
                        chain_to_use = st.session_state.get('selected_chain', 'A')
                        st.info(f"📎 {pdb_file.name}: Using specified chain {chain_to_use}")
                    else:
                        # Auto mode: use first chain
                        chain_to_use = structure_info['chains'][0]['id']
                        st.info(f"📎 {pdb_file.name}: Auto-selected chain {chain_to_use} ({len(structure_info['chains'])} chains available)")
                
                success, msg, cleaned_path = st.session_state.pdb_manager.clean_pdb(
                    pdb_file,
                    chain=chain_to_use,  # Use chain based on user preference
                    remove_water=True,
                    remove_heteroatoms=False # KEEP LIGANDS for analysis
                )
                if cleaned_path:
                    cleaned_files.append(cleaned_path)
            except Exception as e:
                st.error(f"Error cleaning {pdb_file.name}: {str(e)}")
                logger.error(f"Error cleaning {pdb_file.name}: {str(e)}")
                continue
        
        
        progress_bar.progress(0.5)
        
        check_cancel("align")
        # Step 3: Run Mustang alignment
        status_text.text("⚙️ Step 3/4: Running Mustang alignment...")
        
        output_dir = Path('results') / 'latest_run'
        
        # CRITICAL: Clean the output directory before each new run
        # Stale files from previous runs cause Bio3D to fail or produce wrong results
        # NOTE: We delete files individually instead of rmtree because Windows may
        # lock the directory if another process (R, Streamlit watcher) has a handle on it
        if output_dir.exists():
            for f in output_dir.iterdir():
                try:
                    if f.is_file():
                        f.unlink()
                    elif f.is_dir():
                        shutil.rmtree(f, ignore_errors=True)
                except PermissionError:
                    pass  # Skip locked files — they'll be overwritten anyway
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Always clear alignment cache for fresh runs
        cached_run_alignment.clear()
              
        success, msg, result_dir = cached_run_alignment(
            st.session_state.mustang_runner,
            cleaned_files,
            output_dir
        )
        
        if not success:
            st.error(f"Mustang alignment failed: {msg}")
            return
            
        # KEY FIX: Ensure input PDBs are present in the result directory
        # This is needed because cached runs might skip the MustangRunner step where copying happens
        for pdb_file in cleaned_files:
            dest_path = result_dir / pdb_file.name
            if not dest_path.exists():
                try:
                    shutil.copy2(pdb_file, dest_path)
                except Exception as e:
                    logger.warning(f"Failed to copy {pdb_file.name} to results: {e}")
        
        progress_bar.progress(0.75)
        
        check_cancel("viz")
        # Step 4: Analyze results
        status_text.text("📊 Step 4/4: Generating visualizations...")
        
        run_id = f"run_{int(datetime.now().timestamp())}"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        name = f"Analysis of {len(st.session_state.pdb_ids)} structures ({datetime.now().strftime('%H:%M')})"
        
        success, msg = process_result_directory(result_dir, st.session_state.pdb_ids, run_id=run_id, timestamp=timestamp, name=name)
        
        if not success:
            st.error(f"Analysis failed: {msg}")
            # Diagnostic info
            if result_dir and result_dir.exists():
                logger.error(f"Diagnostic - result_dir files: {list(result_dir.iterdir())}")
            return
            
        progress_bar.progress(1.0)
        status_text.text("✅ Analysis complete!")
        cancel_container.empty()
        st.success("Analysis completed successfully!")
        
        # Meta info for auto-recovery sync
        meta = st.session_state.get('metadata', {})
        meta['input_method'] = st.session_state.get('input_method_radio', 'Manual Entry')
        meta['example_name'] = st.session_state.get('example_select')
        
        saved = st.session_state.history_db.save_run(
            run_id, 
            name, 
            st.session_state.pdb_ids, 
            result_dir,
            metadata=meta
        )
        if saved:
            st.toast(f"Saved to history: {name}", icon="✅")
                      
        st.balloons()
        st.rerun()
        
    except Exception as e:
        st.error(f"Error during analysis: {str(e)}")
        logger.error(f"Analysis error: {str(e)}", exc_info=True)


def render_dashboard() -> None:
    """
    Render the main Analysis Dashboard (Mission Control).
    
    Handles both the pre-analysis configuration (ID entry, upload)
    and the post-analysis result display.
    """
    
    # 1. Dashboard Header
    st.caption("Perform rigorous structural alignment, RMSD calculations, and phylogenetic analysis.")

    results = st.session_state.get('results')

    # Top Inputs if not analyzed
    if not results:
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
                        success, msg, path = st.session_state.pdb_manager.save_uploaded_file(uploaded_file)
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

    # 2. Status & Metrics Bar
    st.divider()
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric("Proteins Loaded", len(st.session_state.pdb_ids))
    with col_m2:
        status = "Analysis Complete" if st.session_state.results else "Ready to Run" 
        if not st.session_state.results and not st.session_state.pdb_ids: status = "Waiting for Input"
        st.metric("System Status", status)
    with col_m3:
        if st.session_state.results:
             try:
                df = st.session_state.results.get('rmsd_df')
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
            if 'chain_info' in st.session_state:
                del st.session_state.chain_info
            # Clear all @st.cache_data caches so new proteins get fresh runs
            st.cache_data.clear()
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
            if not st.session_state.get('metadata_fetched'):
                with st.spinner("Fetching protein metadata..."):
                    try:
                        metadata = cached_fetch_metadata(st.session_state.pdb_manager, st.session_state.pdb_ids)
                        st.session_state.metadata = metadata
                        st.session_state.metadata_fetched = True
                    except Exception as e:
                        st.error(f"Metadata fetch failed: {str(e)}")
                        st.session_state.metadata = {}
            
            if st.session_state.metadata:
                data = []
                for pid in st.session_state.pdb_ids:
                    info = st.session_state.metadata.get(pid, {})
                    data.append({
                        'PDB ID': pid,
                        'Title': info.get('title', 'N/A'),
                        'Organism': info.get('organism', 'N/A'),
                        'Method': info.get('method', 'N/A'),
                        'Resolution': info.get('resolution', 'N/A')
                    })
                
                df = pd.DataFrame(data)
                st.dataframe(
                    df, 
                    column_config={
                        "PDB ID": st.column_config.TextColumn(width="small"),
                        "Title": st.column_config.TextColumn(width="large"),
                    },
                    hide_index=True,
                    use_container_width=True
                )
        
        # Action Buttons
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("🔍 Analyze Chains", help="Check chain information before running alignment", use_container_width=True):
                with st.spinner("Analyzing structures..."):
                    download_results = cached_batch_download(
                        st.session_state.pdb_manager,
                        st.session_state.pdb_ids
                    )
                    chain_info = {}
                    for pdb_id, (success, msg, path) in download_results.items():
                        if success and path:
                            try:
                                info = cached_analyze_structure(st.session_state.pdb_manager, path)
                                chain_info[pdb_id] = info
                            except Exception as e:
                                st.error(f"Error analyzing {pdb_id}: {str(e)}")
                    st.session_state.chain_info = chain_info
        
        with col2:
             if st.button("▶️ Run Analysis", type="primary", use_container_width=True):
                run_analysis()
        
        # Chain Info Display
        if 'chain_info' in st.session_state and st.session_state.chain_info:
            st.success("✓ Chain analysis complete!")
            with st.expander("🔗 Chain Information", expanded=True):
                for pdb_id, info in st.session_state.chain_info.items():
                    st.markdown(f"**{pdb_id}**")
                    cols = st.columns(len(info['chains']) if len(info['chains']) <= 5 else 5)
                    for idx, chain in enumerate(info['chains']):
                        with cols[idx % 5]:
                            st.metric(f"Chain {chain['id']}", f"{chain['residue_count']} residues")
                    st.divider()

    # 4. Console
    log_file = st.session_state.get('log_file')
    render_console(Path(log_file) if log_file else None)
