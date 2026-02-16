import streamlit as st
import pandas as pd
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

def init_session_state():
    """Initialize Streamlit session state variables."""
    # ... (existing init)
    if 'ligand_analyzer' not in st.session_state:
        st.session_state.ligand_analyzer = LigandAnalyzer(st.session_state.config)

# ... (inside display_results)

    # Tabs for different result views
    tab1, tab2, tab3, tab_ligand, tab4, tab6, tab5 = st.tabs([
        "📈 RMSD Analysis", 
        "🌳 Phylogenetic Tree",
        "🧬 3D Visualization",
        "💊 Ligands",
        "🔍 Clusters", 
        "🧬 Sequences",
        "📁 Downloads"
    ])
    
    # ... (tab1, tab2, tab3)
    
    with tab_ligand:
        st.subheader("💊 Ligand & Interaction Analysis")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            # Select Protein
            selected_pdb_ligand = st.selectbox(
                "Select Protein Structure", 
                st.session_state.pdb_ids,
                key="ligand_pdb_select"
            )
            
            # Find path for selected PDB
            # We need to find the CLEANED file path corresponding to this ID
            # It should be in the results directory
            result_dir = st.session_state.results['result_dir']
            pdb_path = list(result_dir.glob(f"*{selected_pdb_ligand}*.pdb"))[0] if list(result_dir.glob(f"*{selected_pdb_ligand}*.pdb")) else None
            
            if pdb_path:
                # Find Ligands
                ligands = st.session_state.ligand_analyzer.get_ligands(pdb_path)
                
                if not ligands:
                    st.info("No ligands found in this structure (excluding water/ions).")
                else:
                    st.success(f"Found {len(ligands)} ligands")
                    
                    # Create labels for dropdown
                    ligand_options = {f"{l['name']} ({l['id']})": l for l in ligands}
                    selected_ligand_name = st.selectbox("Select Ligand", list(ligand_options.keys()))
                    
                    selected_ligand = ligand_options[selected_ligand_name]
                    
                    # Calculate Interactions
                    if st.button("Analyze Interactions"):
                        interactions = st.session_state.ligand_analyzer.calculate_interactions(
                            pdb_path, 
                            selected_ligand['id']
                        )
                        st.session_state.current_interactions = interactions
                        st.session_state.current_ligand_pdb = pdb_path
            else:
                st.error("PDB file not found.")

        with col2:
            if 'current_interactions' in st.session_state:
                interactions = st.session_state.current_interactions
                pdb_path = st.session_state.current_ligand_pdb
                
                if 'error' in interactions:
                    st.error(interactions['error'])
                else:
                    st.markdown(f"### Binding Site: **{interactions['ligand']}**")
                    
                    # 3D View
                    show_ligand_view_in_streamlit(
                        pdb_path, 
                        interactions, 
                        width=700, 
                        height=500,
                        key="ligand_3d"
                    )
                    
                    # Interaction Table
                    st.markdown("#### Interacting Residues (< 5Å)")
                    if interactions['interactions']:
                        df_int = pd.DataFrame(interactions['interactions'])
                        st.dataframe(
                            df_int[['residue', 'chain', 'resi', 'distance', 'type']],
                            use_container_width=True
                        )
                    else:
                        st.info("No residues found within cutoff distance.")

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
            runs = st.session_state.history_db.get_all_runs()
            if not runs:
                st.info("No saved runs found.")
            else:
                for run in runs:
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.caption(f"**{run['name']}**\n{run['timestamp']}")
                    with col2:
                        if st.button("📂", key=f"load_{run['id']}", help="Load this run"):
                            load_run_from_history(run['id'])
                            st.rerun()
                    with col3:
                        if st.button("🗑️", key=f"del_{run['id']}", help="Delete this run"):
                            if st.session_state.history_db.delete_run(run['id']):
                                st.rerun()
                    st.divider()
        
        st.divider()
        
        # Input method selection
        input_method = st.radio(
            "Input Method",
            ["Manual Entry", "Load Example", "Upload ID List", "Upload PDB Structure(s)"],
            help="Choose how to provide PDB IDs"
        )
        
        pdb_ids = []
        uploaded_mode = False
        
        if input_method == "Manual Entry":
            pdb_input = st.text_area(
                "Enter PDB IDs (one per line)",
                height=150,
                placeholder="e.g.\n4YZI\n3UG9\n7E6X",
                help="Enter 2-20 PDB IDs, one per line"
            )
            if pdb_input:
                pdb_ids = [pid.strip().upper() for pid in pdb_input.strip().split('\n') if pid.strip()]
        
        elif input_method == "Load Example":
            example_name = st.selectbox("Select Example Dataset", list(EXAMPLES.keys()))
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
            if st.session_state.pdb_ids:
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


def load_run_from_history(run_id: str):
    """Load a past run from the database."""
    run = st.session_state.history_db.get_run(run_id)
    if not run:
        st.error("Run not found in database.")
        return

    result_path = Path(run['result_path'])
    if not result_path.exists():
        st.error(f"Result directory not found: {result_path}")
        return

    st.session_state.pdb_ids = run['pdb_ids']
    
    with st.spinner("Restoring analysis results..."):
        success, msg = process_result_directory(result_path, run['pdb_ids'])
        if success:
            st.success(f"Loaded run: {run['name']}")
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
            return
            
        progress_bar.progress(1.0)
        status_text.text("✅ Analysis complete!")
        st.success("Analysis completed successfully!")
        
        # Auto-save option or manual save button
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("💾 Save to History", use_container_width=True):
                 run_id = f"run_{int(datetime.now().timestamp())}"
                 name = f"Analysis {len(st.session_state.pdb_ids)} Structures"
                 saved = st.session_state.history_db.save_run(
                     run_id, 
                     name, 
                     st.session_state.pdb_ids, 
                     result_dir
                 )
                 if saved:
                     st.toast("Run saved to history!", icon="💾")
                 else:
                     st.error("Failed to save run")
                     
        st.balloons()
        
    except Exception as e:
        st.error(f"Error during analysis: {str(e)}")
        st.session_state.logger.error(f"Analysis error: {str(e)}", exc_info=True)


def display_results():
    """Display analysis results."""
    st.divider()
    st.header("📊 Results")
    
    results = st.session_state.results
    
    # Tabs for different result views
    tab1, tab2, tab3, tab_ligand, tab4, tab6, tab5 = st.tabs([
        "📈 RMSD Analysis", 
        "🌳 Phylogenetic Tree",
        "🧬 3D Visualization",
        "💊 Ligands",
        "🔍 Clusters", 
        "🧬 Sequences",
        "📁 Downloads"
    ])
    
    with tab1:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("RMSD Heatmap")
            with st.expander("❓ What is RMSD & How to read this?", expanded=False):
                st.markdown("""
                ### **1. What is RMSD?**
                **RMSD (Root Mean Square Deviation)** is the standard measure of structural difference between proteins. It calculates the average distance between matching atoms in two superimposed structures.
                *   **Unit**: Angstroms (Å). 1 Å = 0.1 nanometers.
                
                ### **2. How to read the Heatmap:**
                This grid compares every protein against every other protein.
                *   **🟦 Blue (Low RMSD, e.g., < 2.0 Å)**: The structures are **very similar**. They likely share the same function and evolutionary origin.
                *   **🟥 Red (High RMSD, e.g., > 2.0 Å)**: The structures are **different**. They may have diverged significantly or look completely different.
                *   **Diagonal**: Always 0.00, because a protein compared to itself has 0 difference.
                """)
            
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
        with st.expander("❓ What is RMSF & How to read this?", expanded=False):
            st.markdown("""
            ### **1. What is RMSF?**
            **RMSF (Root Mean Square Fluctuation)** measures how much each *individual* amino acid moves around in space.
            *   **Rigid**: Parts that don't move much (the core structure).
            *   **Flexible**: Parts that wobble or flap around (loops, tails).
            
            ### **2. How to read the Chart:**
            *   **X-Axis**: The sequence of amino acids (Position 1, 2, 3...).
            *   **Y-Axis (RMSF Å)**: How much that position moved. Higher = More Flexible.
            *   **Peaks 📈**: Identify flexible loops or disordered regions. These are often where ligands bind or interactions happen!
            *   **Valleys 📉**: The stable core of the protein.
            """)
        
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

    with tab2:
        st.subheader("Phylogenetic Tree (UPGMA)")
        with st.expander("❓ What is this Tree & How to read it?", expanded=False):
            st.markdown("""
            ### **1. What is a Structural Tree?**
            Unlike traditional evolutionary trees based on DNA sequences, this tree groups proteins based on their **3D shape similarity** (Structural Phylogeny).
            *   **Clustering**: Proteins on the same branch are "structural siblings." They look very similar in 3D space.
            *   **Distance**: The horizontal length of the branches represents the RMSD distance. **Longer branches = distinct structures**.
            
            ### **2. Why use UPGMA?**
            UPGMA (Unweighted Pair Group Method with Arithmetic Mean) is a simple clustering algorithm that assumes a constant rate of evolution. It's great for visualizing hierarchical relationships in data.
            """)
            
        if results.get('tree_fig'):
            st.plotly_chart(results['tree_fig'], use_container_width=True)
        elif results.get('tree_path') and results['tree_path'].exists():
            st.image(str(results['tree_path']), use_container_width=True)
        else:
            st.warning("Phylogenetic tree not available")
    
    with tab3:
        st.subheader("3D Structural Superposition")
        
        with st.expander("❓ What is Superposition & Interpretation Guide", expanded=False):
            st.markdown("""
            ### **1. What is Superposition?**
            Superposition is the process of attempting to **overlap** multiple protein structures on top of each other to find the "best fit." This allows us to see exactly where they differ.
            *   **Aligned Regions**: Parts of the proteins that overlap perfectly usually have the same function.
            *   **Divergent Regions**: Parts that stick out or don't overlap are variable regions (often loops or surface areas).

            ### **2. Visualization Styles:**
            *   **Cartoon**: Simplifies the protein into ribbons (helices) and arrows (sheets). Best for seeing the overall "fold" or shape.
            *   **Stick**: Shows the bonds between atoms. Useful for seeing side-chains.
            *   **Surface**: Shows the outer "skin" of the molecule. Good for seeing pockets.
            """)
            
        st.info("💡 Explore different representations of the aligned structures. Rotate and zoom to investigate.")
        
        if results.get('alignment_pdb') and results['alignment_pdb'].exists():
            try:
                pdb_path = results['alignment_pdb']
                
                # Row 1
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Cartoon (Secondary Structure)**")
                    show_structure_in_streamlit(pdb_path, width=400, height=300, style='cartoon', key='view_cartoon')
                with col2:
                    st.markdown("**Sphere (Spacefill)**")
                    show_structure_in_streamlit(pdb_path, width=400, height=300, style='sphere', key='view_sphere')
                    
                # Row 2
                col3, col4 = st.columns(2)
                with col3:
                    st.markdown("**Stick (Bonds & Atoms)**")
                    show_structure_in_streamlit(pdb_path, width=400, height=300, style='stick', key='view_stick')
                with col4:
                    st.markdown("**Line/Trace (Backbone)**")
                    show_structure_in_streamlit(pdb_path, width=400, height=300, style='line', key='view_line')
                
                st.caption("""
                **Controls:**
                - **Left click + drag**: Rotate
                - **Right click + drag**: Zoom  
                - **Scroll**: Zoom in/out
                - Each structure is colored differently for easy identification
                """)
            except Exception as e:
                st.error(f"Failed to load 3D viewer: {str(e)}")
                st.info("You can download the alignment.pdb file and open it in PyMOL or Chimera")
        else:
            st.warning("3D visualization not available")

    with tab_ligand:
        st.subheader("💊 Ligand & Interaction Analysis")
        
        with st.expander("❓ What are Ligands & How to read this?", expanded=True):
            st.markdown("""
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
            """)
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            # Select Protein
            selected_pdb_ligand = st.selectbox(
                "Select Protein Structure", 
                st.session_state.pdb_ids,
                key="ligand_pdb_select"
            )
            
            # Find path for selected PDB
            # We look for the file in the result directory
            result_dir = st.session_state.results['result_dir']
            
            # Try multiple patterns to find the file
            possible_files = [
                result_dir / f"{selected_pdb_ligand}.pdb",
                result_dir / f"{selected_pdb_ligand.lower()}.pdb",
                result_dir / f"{selected_pdb_ligand.upper()}.pdb"
            ]
            
            # Also try glob as fallback
            pdb_path = None
            for p in possible_files:
                if p.exists():
                    pdb_path = p
                    break
            
            if not pdb_path:
                # Fallback to glob
                matches = list(result_dir.glob(f"*{selected_pdb_ligand}*.pdb"))
                if matches:
                    pdb_path = matches[0]
            
            if pdb_path:
                # Find Ligands
                ligands = st.session_state.ligand_analyzer.get_ligands(pdb_path)
                
                if not ligands:
                    st.info("No ligands found in this structure (excluding water/ions).")
                else:
                    st.success(f"Found {len(ligands)} ligands")
                    
                    # Create labels for dropdown
                    ligand_options = {f"{l['name']} ({l['id']})": l for l in ligands}
                    selected_ligand_name = st.selectbox("Select Ligand", list(ligand_options.keys()))
                    
                    selected_ligand = ligand_options[selected_ligand_name]
                    
                    # Calculate Interactions
                    if st.button("Analyze Interactions"):
                        interactions = st.session_state.ligand_analyzer.calculate_interactions(
                            pdb_path, 
                            selected_ligand['id']
                        )
                        st.session_state.current_interactions = interactions
                        st.session_state.current_ligand_pdb = pdb_path
            else:
                st.error(f"PDB file not found for {selected_pdb_ligand}")
                # Debug info
                st.warning(f"Looked in: {result_dir}")
                st.info("Available files:")
                files = list(result_dir.glob("*.pdb"))
                if files:
                    st.code("\n".join([f.name for f in files]))
                else:
                    st.text("No .pdb files found in results directory.")

        with col2:
            if 'current_interactions' in st.session_state:
                interactions = st.session_state.current_interactions
                pdb_path = st.session_state.current_ligand_pdb
                
                if 'error' in interactions:
                    st.error(interactions['error'])
                else:
                    st.markdown(f"### Binding Site: **{interactions['ligand']}**")
                    
                    # 3D View
                    show_ligand_view_in_streamlit(
                        pdb_path, 
                        interactions, 
                        width=700, 
                        height=500,
                        key="ligand_3d"
                    )
                    
                    # Interaction Table
                    st.markdown("#### Interacting Residues (< 5Å)")
                    if interactions['interactions']:
                        df_int = pd.DataFrame(interactions['interactions'])
                        st.dataframe(
                            df_int[['residue', 'chain', 'resi', 'distance', 'type']],
                            use_container_width=True
                        )
                    else:
                        st.info("No residues found within cutoff distance.")

    with tab6:
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
    
    with tab4:
        st.subheader("Structural Clusters")
        clusters = results['clusters']
        
        if clusters:
            for cluster_id, members in clusters.items():
                st.write(f"**Cluster {cluster_id}**: {', '.join(members)}")
        else:
            st.info("No distinct clusters identified (all structures are similar)")
    
    with tab5:
        st.subheader("Data Downloads")
        
        # Report Generation
        st.markdown("### 📄 Analysis Report")
        if st.button("Generate PDF Report", help="Create a comprehensive PDF report of these results"):
            with st.spinner("Generating report..."):
                try:
                    report_path = st.session_state.report_generator.generate_report(
                        st.session_state.results,
                        st.session_state.pdb_ids
                    )
                    st.success(f"Report generated: {report_path.name}")
                    
                    with open(report_path, "rb") as f:
                        st.download_button(
                            "⬇️ Download PDF Report",
                            f,
                            file_name=report_path.name,
                            mime="application/pdf"
                        )
                except Exception as e:
                    st.error(f"Failed to generate report: {e}")
        
        st.divider()
        st.markdown("### 📂 Raw Data")
        
        result_dir = results['result_dir']
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Download RMSD CSV
            csv_data = results['rmsd_df'].to_csv()
            st.download_button(
                label="📥 RMSD Matrix (CSV)",
                data=csv_data,
                file_name="rmsd_matrix.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            # Download heatmap
            if results['heatmap_path'].exists():
                with open(results['heatmap_path'], 'rb') as f:
                    st.download_button(
                        label="📥 RMSD Heatmap (PNG)",
                        data=f.read(),
                        file_name="rmsd_heatmap.png",
                        mime="image/png",
                        use_container_width=True
                    )
        
        with col2:
            # Download phylogenetic tree
            if results.get('tree_path') and results['tree_path'].exists():
                with open(results['tree_path'], 'rb') as f:
                    st.download_button(
                        label="📥 Phylogenetic Tree (PNG)",
                        data=f.read(),
                        file_name="phylogenetic_tree.png",
                        mime="image/png",
                        use_container_width=True
                    )
            
            # Download Newick tree
            if results.get('newick_path') and results['newick_path'].exists():
                with open(results['newick_path'], 'r') as f:
                    st.download_button(
                        label="📥 Tree Format (Newick)",
                        data=f.read(),
                        file_name="tree.newick",
                        mime="text/plain",
                        use_container_width=True
                    )
        
        st.divider()
        st.info(f"📂 All results saved to: `{result_dir}`")


if __name__ == "__main__":
    main()
