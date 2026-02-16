import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from pathlib import Path
import logging
import shutil
import time
from datetime import datetime
import re

from src.backend.pdb_manager import PDBManager
from src.backend.mustang_runner import MustangRunner
from src.backend.rmsd_analyzer import RMSDAnalyzer
from src.backend.phylo_tree import PhyloTreeGenerator
from src.backend.sequence_viewer import SequenceViewer
from src.backend.report_generator import ReportGenerator
from src.backend.ligand_analyzer import LigandAnalyzer
from src.backend.structure_viewer import show_structure_in_streamlit, show_ligand_view_in_streamlit
from src.backend.database import HistoryDatabase
from src.utils.logger import setup_logger
from src.utils.config_loader import load_config
from examples.protein_sets import EXAMPLES


# Page configuration
st.set_page_config(
    page_title="Mustang Structural Alignment Pipeline",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
# Load custom CSS
def load_css():
    css_file = Path("static/style.css")
    if css_file.exists():
        with open(css_file) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()


@st.cache_data(show_spinner=False)
def cached_batch_download(_pdb_manager, pdb_ids):
    """Cached wrapper for batch PDB download."""
    return _pdb_manager.batch_download(pdb_ids, max_workers=4)

@st.cache_data(show_spinner=False)
def cached_analyze_structure(_pdb_manager, file_path):
    """Cached wrapper for structure analysis."""
    return _pdb_manager.analyze_structure(file_path)

@st.cache_data(show_spinner=False)
def cached_run_alignment(_mustang_runner, pdb_files, run_dir):
    """Cached wrapper for Mustang alignment."""
    return _mustang_runner.run_alignment(pdb_files, run_dir)

@st.cache_data(show_spinner=False)
def cached_calculate_rmsd(_rmsd_analyzer, alignment_file, pdb_files):
    """Cached wrapper for RMSD calculation."""
    return _rmsd_analyzer.calculate_rmsd_matrix(alignment_file, pdb_files)

@st.cache_data(show_spinner=False)
def cached_fetch_metadata(_pdb_manager, pdb_ids):
    """Cached wrapper for metadata fetching."""
    return _pdb_manager.fetch_metadata(pdb_ids)

def init_session_state():
    """Initialize Streamlit session state variables."""
    if 'config' not in st.session_state:
        st.session_state.config = load_config()
        st.session_state.logger = setup_logger()
    
    if 'pdb_manager' not in st.session_state:
        st.session_state.pdb_manager = PDBManager(st.session_state.config)
    
    if 'mustang_runner' not in st.session_state:
        st.session_state.mustang_runner = MustangRunner(st.session_state.config)
    
    if 'rmsd_analyzer' not in st.session_state:
        st.session_state.rmsd_analyzer = RMSDAnalyzer(st.session_state.config)
    
    if 'sequence_viewer' not in st.session_state:
        st.session_state.sequence_viewer = SequenceViewer()
        
    if 'report_generator' not in st.session_state:
        st.session_state.report_generator = ReportGenerator(Path('results') / 'latest_run')
    
    if 'pdb_ids' not in st.session_state:
        st.session_state.pdb_ids = []
    
    if 'results' not in st.session_state:
        st.session_state.results = None

    if 'ligand_analyzer' not in st.session_state:
        st.session_state.ligand_analyzer = LigandAnalyzer(st.session_state.config)
        
    if 'history_db' not in st.session_state:
        st.session_state.history_db = HistoryDatabase()

    if 'auto_recovered' not in st.session_state:
        st.session_state.auto_recovered = False
        
    # Auto-recovery: If results is None, try to load the latest successful run
    # ONLY if we haven't already attempted recovery in this session
    if st.session_state.get('results') is None and not st.session_state.auto_recovered:
        st.session_state.auto_recovered = True # Mark as attempted (session-persistent)
        st.session_state.loading_latest = True
        latest_run = st.session_state.history_db.get_latest_run()
        if latest_run:
            load_run_from_history(latest_run['id'], is_auto=True)
        st.session_state.loading_latest = False


def main():
    """Main application function."""
    init_session_state()
    
    # Header
    st.markdown('<p class="main-header">🧬 Mustang Structural Alignment Pipeline</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Automated Multiple Structural Alignment for Any Protein Family</p>', unsafe_allow_html=True)
    
    # Sidebar
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
            # Handle stale session state where HistoryDatabase might be an old instance
            try:
                runs = st.session_state.history_db.get_all_runs(limit=6)
            except TypeError:
                # Fallback for old instances pending reload
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
                                load_run_from_history(run['id'])
                        
                        # Use a small delete button below or next to it
                        if st.button("🗑️ Delete", key=f"del_{run['id']}", use_container_width=True):
                            if st.session_state.history_db.delete_run(run['id']):
                                st.rerun()
                        st.divider()
                
                if st.button("🗑️ Clear All History", use_container_width=True, type="secondary"):
                    for run in runs:
                        st.session_state.history_db.delete_run(run['id'])
                    st.rerun()
        
        st.divider()
        
        # Input method selection
        input_method = st.radio(
            "Input Method",
            ["Manual Entry", "Load Example", "Upload ID List", "Upload PDB Structure(s)"],
            help="Choose how to provide PDB IDs",
            key="input_method_radio"
        )
        
        pdb_ids = []
        uploaded_mode = False
        
        if input_method == "Manual Entry":
            pdb_input = st.text_area(
                "Enter PDB IDs (one per line)",
                height=150,
                placeholder="e.g.\n4YZI\n3UG9\n7E6X",
                help="Enter 2-20 PDB IDs, one per line",
                key="manual_pdb_input"
            )
            if pdb_input:
                pdb_ids = [pid.strip().upper() for pid in pdb_input.strip().split('\n') if pid.strip()]
        
        elif input_method == "Load Example":
            example_name = st.selectbox("Select Example Dataset", list(EXAMPLES.keys()), key="example_select")
            if example_name:
                pdb_ids = EXAMPLES[example_name]
                st.info(f"Loaded {len(pdb_ids)} proteins from {example_name}")
        
        elif input_method == "Upload ID List":
            uploaded_file = st.file_uploader(
                "Upload text file with PDB IDs",
                type=['txt'],
                help="One PDB ID per line"
            )
            if uploaded_file:
                content = uploaded_file.read().decode('utf-8')
                pdb_ids = [pid.strip().upper() for pid in content.strip().split('\n') if pid.strip()]

        elif input_method == "Upload PDB Structure(s)":
            uploaded_files = st.file_uploader(
                "Upload .pdb files",
                type=['pdb'],
                accept_multiple_files=True,
                help="Directly upload PDB structure files"
            )
            
            if uploaded_files:
                uploaded_mode = True
                for up_file in uploaded_files:
                    success, msg, path = st.session_state.pdb_manager.save_uploaded_file(up_file)
                    if success:
                        pdb_ids.append(path.stem) # Use filename as ID
                    else:
                        st.error(f"Failed to save {up_file.name}: {msg}")
                
                if pdb_ids:
                    st.success(f"Successfully processed {len(pdb_ids)} uploaded structures")
        
        if pdb_ids:
            valid_ids = []
            invalid_ids = []
            
            for pid in pdb_ids:
                if uploaded_mode or st.session_state.pdb_manager.validate_pdb_id(pid):
                    valid_ids.append(pid)
                else:
                    invalid_ids.append(pid)
            
            if valid_ids:
                if set(valid_ids) != set(st.session_state.pdb_ids):
                    st.session_state.pdb_ids = valid_ids
                    st.session_state.results = None
                    st.session_state.metadata_fetched = False
                    st.session_state.metadata = {}
                    if 'chain_info' in st.session_state:
                        del st.session_state.chain_info
                    st.toast("Updated protein selection", icon="🔄")
                
                st.success(f"✓ {len(valid_ids)} valid PDB IDs")
            
            if invalid_ids:
                st.warning(f"⚠ Invalid IDs: {', '.join(invalid_ids)}")
        else:
            # ONLY reset if NOT just recovered
            if st.session_state.pdb_ids and not st.session_state.get('loading_latest'):
                st.session_state.pdb_ids = []
                st.session_state.results = None
                st.session_state.metadata_fetched = False
                st.session_state.metadata = {}
                if 'chain_info' in st.session_state:
                    del st.session_state.chain_info
        
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
    
    # Main content area
    if not st.session_state.pdb_ids:
        # Welcome screen
        st.info("👈 Start by entering PDB IDs or loading an example dataset from the sidebar")
        
        st.subheader("About This Pipeline")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("### 📥 Input")
            st.write("Enter PDB IDs for any protein family you want to analyze")
        
        with col2:
            st.markdown("### ⚙️ Process")
            st.write("Automated download → cleaning → Mustang alignment → analysis")
        
        with col3:
            st.markdown("### 📊 Output")
            st.write("RMSD matrices, phylogenetic trees, visualizations, reports")
        
        st.divider()
        
        st.subheader("Example Use Cases")
        st.write("""
        - **GPCR Analysis**: Compare channelrhodopsin structures
        - **Enzyme Studies**: Analyze kinase or protease families
        - **Antibody Engineering**: Compare antibody variable regions
        - **Evolutionary Studies**: Trace protein structural evolution
        """)
        
    else:
        # Analysis interface
        st.subheader(f"Analysis: {len(st.session_state.pdb_ids)} Proteins")
        
        # Display selected proteins
        with st.expander("📋 Selected Proteins", expanded=True):
            if not st.session_state.get('metadata_fetched'):
                with st.spinner("Fetching protein metadata..."):
                    try:
                        # Use cached metadata fetcher
                        metadata = cached_fetch_metadata(st.session_state.pdb_manager, st.session_state.pdb_ids)
                        st.session_state.metadata = metadata
                        st.session_state.metadata_fetched = True
                    except Exception as e:
                        st.error(f"Could not fetch metadata: {str(e)}")
                        logger.error(f"Metadata fetch failed: {str(e)}")
                        st.session_state.metadata = {}
            
            if st.session_state.metadata:
                st.success(f"Fetched metadata for {len(st.session_state.metadata)} proteins")
            else:
                st.warning("No metadata available. Using basic IDs.")
            
            # Create a DataFrame for display
            if hasattr(st.session_state, 'metadata') and st.session_state.metadata:
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
            else:
                # Fallback to simple list
                cols = st.columns(5)
                for idx, pdb_id in enumerate(st.session_state.pdb_ids):
                    cols[idx % 5].code(pdb_id)
        
        # Chain Analysis Button
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("🔍 Analyze Chains", help="Check chain information before running alignment"):
                with st.spinner("Analyzing structures..."):
                    # Download PDbs if not already downloaded
                    # Use CACHED download
                    download_results = cached_batch_download(
                        st.session_state.pdb_manager,
                        st.session_state.pdb_ids
                    )
                    
                    # Analyze each structure
                    chain_info = {}
                    for pdb_id, (success, msg, path) in download_results.items():
                        if success and path:
                            try:
                                # Use CACHED analysis
                                info = cached_analyze_structure(st.session_state.pdb_manager, path)
                                chain_info[pdb_id] = info
                            except Exception as e:
                                st.error(f"Error analyzing {pdb_id}: {str(e)}")
                    
                    st.session_state.chain_info = chain_info
        
        # Display chain information if available
        if 'chain_info' in st.session_state and st.session_state.chain_info:
            st.success("✓ Chain analysis complete!")
            
            with st.expander("🔗 Chain Information", expanded=True):
                for pdb_id, info in st.session_state.chain_info.items():
                    st.markdown(f"**{pdb_id}**")
                    if len(info['chains']) > 1:
                        st.warning(f"⚠️ Multiple chains detected ({len(info['chains'])} chains)")
                    
                    # Display chain details in columns
                    cols = st.columns(len(info['chains']) if len(info['chains']) <= 5 else 5)
                    for idx, chain in enumerate(info['chains']):
                        with cols[idx % 5]:
                            st.metric(
                                f"Chain {chain['id']}", 
                                f"{chain['residue_count']} residues"
                            )
                    st.divider()
        
        with col2:
            # Run analysis button
            if st.button("▶️ Run Analysis", type="primary", use_container_width=True):
                run_analysis()
        
        # Display results if available
        if st.session_state.results:
            display_results()


def process_result_directory(result_dir: Path, pdb_ids: list):
    """
    Process a Mustang result directory and generate all analysis artifacts.
    Re-uses existing logic to populate st.session_state.results.
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
        rmsf_values, conservation_labels = st.session_state.rmsd_analyzer.calculate_residue_rmsf(
            alignment_pdb, 
            alignment_afasta
        )
        
        # Store results
        st.session_state.results = {
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
        return True, "Success"
    except Exception as e:
        st.session_state.logger.error(f"Error processing results: {e}", exc_info=True)
        return False, str(e)


def load_run_from_history(run_id: str, is_auto: bool = False):
    """Load a past run from the database."""
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
        process_result_directory(result_path, run['pdb_ids'])
    else:
        with st.spinner("Restoring analysis results..."):
            success, msg = process_result_directory(result_path, run['pdb_ids'])
            if success:
                st.success(f"Loaded run: {run['name']}")
                st.rerun()
            else:
                st.error(f"Failed to load run: {msg}")


def run_analysis():
    """Run the complete analysis pipeline."""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # Step 1: Download PDB files
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
        
        # Step 3: Run Mustang alignment
        status_text.text("⚙️ Step 3/4: Running Mustang alignment...")
        
        output_dir = Path('results') / 'latest_run'
        
        # Check for Force Run flag
        force_rerun = st.session_state.get('force_rerun', False)
        
        # Use CACHED alignment (unless forced)
        if force_rerun:
             # Clear cache for this specific function? 
             # Streamlit cache clearing is global or by function, but we can just bypass it by calling the internal method directly?
             # Or we invalid cache via mutation.
             # Easier: Just run it without cache decorator if possible, or clear specific cache.
             # Actually, best way is to manually clear if requested.
             cached_run_alignment.clear()
             st.toast("Forcing re-run...", icon="🔄")
             
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
        
        # Step 4: Analyze results
        status_text.text("📊 Step 4/4: Generating visualizations...")
        
        success, msg = process_result_directory(result_dir, st.session_state.pdb_ids)
        
        if not success:
            st.error(f"Analysis failed: {msg}")
            # Diagnostic info
            if result_dir and result_dir.exists():
                logger.error(f"Diagnostic - result_dir files: {list(result_dir.iterdir())}")
            return
            
        progress_bar.progress(1.0)
        status_text.text("✅ Analysis complete!")
        st.success("Analysis completed successfully!")
        
        # AUTO-SAVE to history
        run_id = f"run_{int(datetime.now().timestamp())}"
        # Name with protein count and timestamp
        name = f"Analysis of {len(st.session_state.pdb_ids)} structures ({datetime.now().strftime('%H:%M')})"
        
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
        
    except Exception as e:
        st.error(f"Error during analysis: {str(e)}")
        st.session_state.logger.error(f"Analysis error: {str(e)}", exc_info=True)



def render_help_expander(topic):
    """Render educational help expanders."""
    helps = {
        "rmsd": {
            "title": "❓ What is RMSD & How to read this?",
            "content": """
                ### **1. What is RMSD?**
                **RMSD (Root Mean Square Deviation)** is the standard measure of structural difference between proteins. It calculates the average distance between matching atoms in two superimposed structures.
                *   **Unit**: Angstroms (Å). 1 Å = 0.1 nanometers.
                
                ### **2. How to read the Heatmap:**
                This grid compares every protein against every other protein.
                *   **🟦 Blue (Low RMSD, e.g., < 2.0 Å)**: The structures are **very similar**. They likely share the same function and evolutionary origin.
                *   **🟥 Red (High RMSD, e.g., > 2.0 Å)**: The structures are **different**. They may have diverged significantly or look completely different.
                *   **Diagonal**: Always 0.00, because a protein compared to itself has 0 difference.
            """
        },
        "rmsf": {
            "title": "❓ What is RMSF & How to read this?",
            "content": """
                ### **1. What is RMSF?**
                **RMSF (Root Mean Square Fluctuation)** measures how much each individual amino acid moves around in space.
                *   **Rigid**: Parts that don't move much (the core structure).
                *   **Flexible**: Parts that wobble or flap around (loops, tails).
                
                ### **2. How to read the Chart:**
                *   **X-Axis**: The sequence of amino acids (Position 1, 2, 3...).
                *   **Y-Axis (RMSF Å)**: How much that position moved. Higher = More Flexible.
                *   **Peaks 📈**: Identify flexible loops or disordered regions. These are often where ligands bind or interactions happen!
                *   **Valleys 📉**: The stable core of the protein.
            """
        },
        "tree": {
            "title": "❓ What is this Tree & How to read it?",
            "content": """
                ### **1. What is a Structural Tree?**
                Unlike traditional evolutionary trees based on DNA sequences, this tree groups proteins based on their **3D shape similarity** (Structural Phylogeny).
                *   **Clustering**: Proteins on the same branch are "structural siblings." They look very similar in 3D space.
                *   **Distance**: The horizontal length of the branches represents the RMSD distance. **Longer branches = distinct structures**.
                
                ### **2. Why use UPGMA?**
                UPGMA (Unweighted Pair Group Method with Arithmetic Mean) is a simple clustering algorithm that assumes a constant rate of evolution. It's great for visualizing hierarchical relationships in data.
            """
        },
        "clusters": {
            "title": "❓ What are Clusters & How to read this?",
            "content": """
                ### **1. What is Structural Clustering?**
                Clustering is a way to group proteins that are "structurally similar" into families. We use **Hierarchical Clustering (UPGMA)** based on the RMSD values.
                
                ### **2. The RMSD Threshold:**
                This is the "cutoff" distance for forming a group. 
                *   **Low Threshold (e.g., 1.5 Å)**: Only very similar proteins (nearly identical folds) will be grouped together.
                *   **High Threshold (e.g., 5.0 Å)**: Even distantly related proteins (sharing only broad structural features) will be put into the same cluster.
                
                ### **3. Why use this?**
                It helps identify sub-families within a large dataset, making it easier to see which proteins might share specific functionalities or binding properties.
            """
        },
        "superposition": {
            "title": "❓ What is Superposition & Interpretation Guide",
            "content": """
                ### **1. What is Superposition?**
                Superposition is the process of attempting to **overlap** multiple protein structures on top of each other to find the "best fit." This allows us to see exactly where they differ.
                *   **Aligned Regions**: Parts of the proteins that overlap perfectly usually have the same function.
                *   **Divergent Regions**: Parts that stick out or don't overlap are variable regions (often loops or surface areas).

                ### **2. Visualization Styles:**
                *   **Cartoon**: Simplifies the protein into ribbons (helices) and arrows (sheets). Best for seeing the overall "fold" or shape.
                *   **Stick**: Shows the bonds between atoms. Useful for seeing side-chains.
                *   **Surface**: Shows the outer "skin" of the molecule. Good for seeing pockets.
            """
        },
        "ligands": {
            "title": "❓ What are Ligands & How to read this?",
            "content": """
                ### **1. What is a Ligand?**
                A **ligand** is a small molecule (like a drug, hormone, or vitamin) that binds to a specific site on a protein to trigger a function or inhibit it. Think of it as a **key** fitting into a **lock** (the protein).
                
                ### **2. How to use this tool:**
                1.  **Select a Protein**: Choose one of your aligned structures from the dropdown.
                2.  **Select a Ligand**: Pick the specific small molecule found in that structure.
                3.  **Analyze Interactions**: Click the button to calculate which parts of the protein are "touching" the ligand.
                
                ### **3. Understanding the Results:**
                -   **3D View (Right)**: Shows the ligand (colorful sticks) inside its binding pocket.
                    -   The **Green/Blue/Red residues** represent the parts of the protein holding the ligand in place.
                -   **Interaction Table (Bottom Right)**:
                    -   **Residue**: The specific amino acid in the protein chain.
                    -   **Distance (Å)**: How close it is to the ligand. **< 3.5 Å** usually means a strong chemical bond.
                    -   **Type**: The kind of connection (e.g., *Hydrogen Bond* = strong, sticky; *Hydrophobic* = oily/greasy interaction).
            """
        }
    }
    if topic in helps:
        with st.expander(helps[topic]["title"], expanded=False):
            st.markdown(helps[topic]["content"])


def render_rmsd_tab(results):
    """Render the RMSD Analysis tab."""
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("RMSD Heatmap")
        render_help_expander("rmsd")
        
        if results.get('heatmap_fig'):
             st.plotly_chart(results['heatmap_fig'], use_container_width=True)
        elif results['heatmap_path'].exists():
            st.image(str(results['heatmap_path']), use_container_width=True)
    
    with col2:
        st.subheader("Statistics")
        stats = results['stats']
        st.metric("Mean RMSD", f"{stats['mean_rmsd']:.2f} Å")
        st.metric("Median RMSD", f"{stats['median_rmsd']:.2f} Å")
        st.metric("Min RMSD", f"{stats['min_rmsd']:.2f} Å")
        st.metric("Max RMSD", f"{stats['max_rmsd']:.2f} Å")
        st.metric("Std Dev", f"{stats['std_rmsd']:.2f} Å")
    
    st.subheader("RMSD Matrix")
    st.dataframe(results['rmsd_df'].style.background_gradient(cmap='RdYlBu_r'))
    
    st.divider()
    st.subheader("Residue-Level Flexibility (RMSF)")
    render_help_expander("rmsf")
    
    if results.get('rmsf_values'):
        rmsf_data = pd.DataFrame({
            'Residue Position': range(1, len(results['rmsf_values']) + 1),
            'RMSF (Å)': results['rmsf_values']
        })
        
        fig = px.line(
            rmsf_data,
            x='Residue Position',
            y='RMSF (Å)',
            title='Structural Fluctuation per Position',
            template='plotly_white'
        )
        fig.update_traces(line_color='#2196F3', line_width=2)
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Residue RMSF data not available")

def render_phylo_tree_tab(results):
    """Render the Phylogenetic Tree tab."""
    st.subheader("Phylogenetic Tree (UPGMA)")
    render_help_expander("tree")
        
    if results.get('tree_fig'):
        st.plotly_chart(results['tree_fig'], use_container_width=True)
    elif results.get('tree_path') and results['tree_path'].exists():
        st.image(str(results['tree_path']), use_container_width=True)
    else:
        st.warning("Phylogenetic tree not available")


def render_3d_viewer_tab(results):
    """Render the 3D Visualization tab."""
    st.subheader("3D Structural Superposition")
    render_help_expander("superposition")
        
    st.info("💡 Explore different representations of the aligned structures. Rotate and zoom to investigate.")
    
    if results.get('alignment_pdb') and results['alignment_pdb'].exists():
        try:
            pdb_path = results['alignment_pdb']
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Cartoon (Secondary Structure)**")
                show_structure_in_streamlit(pdb_path, width=400, height=300, style='cartoon', key='view_cartoon')
            with col2:
                st.markdown("**Sphere (Spacefill)**")
                show_structure_in_streamlit(pdb_path, width=400, height=300, style='sphere', key='view_sphere')
                
            col3, col4 = st.columns(2)
            with col3:
                st.markdown("**Stick (Bonds & Atoms)**")
                show_structure_in_streamlit(pdb_path, width=400, height=300, style='stick', key='view_stick')
            with col4:
                st.markdown("**Line/Trace (Backbone)**")
                show_structure_in_streamlit(pdb_path, width=400, height=300, style='line', key='view_line')
            
            st.caption("""
            **Controls:**
            - **Left click + drag**: Rotate | **Right click + drag**: Zoom | **Scroll**: Zoom in/out
            - Each structure is colored differently for easy identification
            """)
        except Exception as e:
            st.error(f"Failed to load 3D viewer: {str(e)}")
    else:
        st.warning("3D visualization not available")

def render_ligand_tab(results):
    """Render the Ligand & Interaction Analysis tab."""
    st.subheader("💊 Ligand & Interaction Analysis")
    render_help_expander("ligands")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        selected_pdb_ligand = st.selectbox("Select Protein Structure", st.session_state.pdb_ids, key="ligand_pdb_select")
        result_dir = results['result_dir']
        
        # Try finding the PDB file
        pdb_path = None
        for suffix in ["", ".lower()", ".upper()"]:
            p = result_dir / f"{selected_pdb_ligand}{suffix}.pdb"
            if p.exists():
                pdb_path = p
                break
        
        if not pdb_path:
            matches = list(result_dir.glob(f"*{selected_pdb_ligand}*.pdb"))
            if matches: pdb_path = matches[0]
        
        if pdb_path:
            ligands = st.session_state.ligand_analyzer.get_ligands(pdb_path)
            if not ligands:
                st.info("No ligands found in this structure (excluding water/ions).")
            else:
                st.success(f"Found {len(ligands)} ligands")
                ligand_options = {f"{l['name']} ({l['id']})": l for l in ligands}
                selected_ligand_name = st.selectbox("Select Ligand", list(ligand_options.keys()))
                selected_ligand = ligand_options[selected_ligand_name]
                
                if st.button("Analyze Interactions"):
                    interactions = st.session_state.ligand_analyzer.calculate_interactions(pdb_path, selected_ligand['id'])
                    st.session_state.current_interactions = interactions
                    st.session_state.current_ligand_pdb = pdb_path
        else:
            st.error(f"PDB file not found for {selected_pdb_ligand}")

    with col2:
        if 'current_interactions' in st.session_state:
            interactions = st.session_state.current_interactions
            pdb_path = st.session_state.current_ligand_pdb
            
            if 'error' in interactions:
                st.error(interactions['error'])
            else:
                st.markdown(f"### Binding Site: **{interactions['ligand']}**")
                show_ligand_view_in_streamlit(pdb_path, interactions, width=700, height=500, key="ligand_3d")
                
                st.markdown("#### Interacting Residues (< 5Å)")
                if interactions['interactions']:
                    df_int = pd.DataFrame(interactions['interactions'])
                    st.dataframe(df_int[['residue', 'chain', 'resi', 'distance', 'type']], use_container_width=True)
                else:
                    st.info("No residues found within cutoff distance.")


def render_sequences_tab(results):
    """Render the Multiple Sequence Alignment tab."""
    st.subheader("Multiple Sequence Alignment")
    st.info("🧬 Color code: Red = 100% Identity, Yellow = High Similarity (>70%)")
    
    if results.get('alignment_afasta') and results['alignment_afasta'].exists():
        sequences = st.session_state.sequence_viewer.parse_afasta(results['alignment_afasta'])
        if sequences:
            conservation = st.session_state.sequence_viewer.calculate_conservation(sequences)
            html_view = st.session_state.sequence_viewer.generate_html(sequences, conservation)
            st.components.v1.html(html_view, height=400, scrolling=True)
        else:
            st.error("Failed to parse alignment file")
    else:
        st.warning("Sequence alignment file not found")

def render_clusters_tab(results):
    """Render the Structural Clusters tab."""
    st.subheader("🔍 Structural Clusters")
    render_help_expander("clusters")
    
    rmsd_df = results.get('rmsd_df')
    if rmsd_df is None:
        st.warning("RMSD data not available for clustering.")
        return

    # User Interactive Threshold
    col1, col2 = st.columns([1, 2])
    with col1:
        threshold = st.slider(
            "RMSD Threshold (Å)", 
            min_value=0.1, 
            max_value=10.0, 
            value=3.0, 
            step=0.1,
            help="Structures with RMSD lower than this 'distance' will be grouped together."
        )
    
    # Re-calculate clusters based on interactive threshold
    clusters = st.session_state.rmsd_analyzer.identify_clusters(rmsd_df, threshold=threshold)
    
    if clusters:
        st.markdown(f"Found **{len(clusters)}** distinct structural families at **{threshold} Å** cutoff.")
        
        for cid, members in clusters.items():
            avg_rmsd = 0.0
            if len(members) > 1:
                # Calculate internal average RMSD (homogeneity of cluster)
                subset = rmsd_df.loc[members, members]
                avg_rmsd = subset.values[np.triu_indices(len(members), k=1)].mean()
            
            with st.expander(f"📁 Cluster {cid} ({len(members)} members, Avg RMSD: {avg_rmsd:.2f} Å)", expanded=True):
                # Show members in a nice clean list or table
                member_data = []
                for m in members:
                    # Get metadata if available
                    title = st.session_state.metadata.get(m, {}).get('title', 'Unknown Title') if hasattr(st.session_state, 'metadata') else 'N/A'
                    member_data.append({"PDB ID": m, "Description": title})
                
                st.table(pd.DataFrame(member_data))
    else:
        st.info("No clusters identified with current settings.")

def render_downloads_tab(results):
    """Render the Data Downloads tab."""
    st.subheader("Data Downloads")
    
    st.markdown("### 📄 Analysis Report")
    if st.button("Generate PDF Report", help="Create a comprehensive PDF report"):
        with st.spinner("Generating report..."):
            try:
                report_path = st.session_state.report_generator.generate_report(results, st.session_state.pdb_ids)
                st.success(f"Report generated: {report_path.name}")
                with open(report_path, "rb") as f:
                    st.download_button("⬇️ Download PDF Report", f, file_name=report_path.name, mime="application/pdf")
            except Exception as e:
                st.error(f"Failed to generate report: {e}")
    
    st.divider()
    st.markdown("### 📂 Raw Data")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📥 RMSD Matrix (CSV)", results['rmsd_df'].to_csv(), file_name="rmsd_matrix.csv", mime="text/csv", use_container_width=True)
        if results['heatmap_path'].exists():
            with open(results['heatmap_path'], 'rb') as f:
                st.download_button("📥 RMSD Heatmap (PNG)", f.read(), file_name="rmsd_heatmap.png", mime="image/png", use_container_width=True)
    with col2:
        if results.get('tree_path') and results['tree_path'].exists():
            with open(results['tree_path'], 'rb') as f:
                st.download_button("📥 Phylogenetic Tree (PNG)", f.read(), file_name="phylogenetic_tree.png", mime="image/png", use_container_width=True)
        if results.get('newick_path') and results['newick_path'].exists():
            with open(results['newick_path'], 'r') as f:
                st.download_button("📥 Tree Format (Newick)", f.read(), file_name="tree.newick", mime="text/plain", use_container_width=True)


def display_results():
    """Display analysis results."""
    st.divider()
    st.header("📊 Results")
    results = st.session_state.results
    
    tab_list = [
        ("📈 RMSD Analysis", render_rmsd_tab),
        ("🌳 Phylogenetic Tree", render_phylo_tree_tab),
        ("🧬 3D Visualization", render_3d_viewer_tab),
        ("💊 Ligands", render_ligand_tab),
        ("🔍 Clusters", render_clusters_tab),
        ("🧬 Sequences", render_sequences_tab),
        ("📁 Downloads", render_downloads_tab)
    ]
    
    tabs = st.tabs([t[0] for t in tab_list])
    for tab, (_, render_func) in zip(tabs, tab_list):
        with tab:
            render_func(results)
    
    st.divider()
    st.info(f"📂 All results saved to: `{results['result_dir']}`")


if __name__ == "__main__":
    main()
