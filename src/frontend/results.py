import streamlit as st
from src.frontend.tabs import rmsd, phylo, structure, sequence, clusters, ligand, downloads

def display_results(results=None):
    """Main results display logic with tabs."""
    if results is None:
        results = st.session_state.get('results')
        
    if not results:
        st.warning("No analysis results found. Please run the analysis first.")
        return

    st.success(f"### Analysis Results: {results.get('name', 'Latest Run')}")
    run_id = results.get('id', 'N/A')
    timestamp = results.get('timestamp', 'N/A')
    st.caption(f"Run ID: `{run_id}` | Timestamp: {timestamp}")
    
    # Define tabs
    tab_list = [
        "📊 Summary & RMSD", 
        "🧬 Sequence Alignment", 
        "🌳 Structural Tree", 
        "🔍 Structural Clusters",
        "3D Visualization", 
        "💊 Ligand Hunter",
        "📥 Downloads"
    ]
    
    t1, t2, t3, t4, t5, t6, t7 = st.tabs(tab_list)
    
    with t1:
        rmsd.render_rmsd_tab(results)
        
    with t2:
        sequence.render_sequences_tab(results)
        
    with t3:
        phylo.render_phylo_tree_tab(results)
        
    with t4:
        clusters.render_clusters_tab(results)
        
    with t5:
        structure.render_3d_viewer_tab(results)
        
    with t6:
        ligand.render_ligand_tab(results)
        
    with t7:
        downloads.render_downloads_tab(results)

def render_compact_summary(results=None):
    """Render a high-level summary of results for the dashboard."""
    if results is None:
        results = st.session_state.get('results')
        
    if not results:
        return
        
    st.markdown("### 📊 Latest Analysis Summary")
    
    col1, col2, col3 = st.columns(3)
    stats = results.get('stats', {})
    
    with col1:
        st.metric("Total Structures", len(results.get('pdb_ids', [])))
    with col2:
        st.metric("Mean RMSD", f"{stats.get('mean_rmsd', 0):.2f} Å")
    with col3:
        st.metric("Sequence Length", results.get('sequence_length', 'N/A'))
    
    if st.button("👁️ View Full Detailed Analysis", type="primary", use_container_width=True):
        st.session_state.active_tab = "Results"
        st.rerun()
