import streamlit as st
from typing import Optional, Dict, Any
from src.frontend.tabs import rmsd, sequence, phylo, clusters, structure, ligand, downloads, comparison

def display_results(results: Optional[Dict[str, Any]] = None) -> None:
    """
    Main results display logic with tabs.
    
    Args:
        results: Results dictionary. If None, retrieves from session state.
    """
    if results is None:
        results = st.session_state.get('results')
        
    if not results:
        st.warning("No analysis results found. Please run the analysis first.")
        return

    st.success(f"### Analysis Results: {results.get('name', 'Latest Run')}")
    run_id = results.get('id', 'N/A')
    
    # Ensure id is present in the dictionary for downstream tabs
    if 'id' not in results:
        results['id'] = results.get('run_id', 'latest')
    timestamp = results.get('timestamp', 'N/A')
    st.caption(f"Run ID: `{run_id}` | Timestamp: {timestamp}")
    
    # Define tabs
    tab_list = [
        "📊 Summary & RMSD", 
        "🧬 Sequence Alignment", 
        "🌳 Structural Tree", 
        "🔍 Structural Clusters",
        "🔮 3D Visualization", 
        "💊 Ligand Hunter",
        "🔄 Batch Comparison",
        "📥 Downloads"
    ]
    
    t1, t2, t3, t4, t5, t6, t7, t8 = st.tabs(tab_list)
    
    # Ensure id/metadata is present (Defensive)
    if 'id' not in results:
        results['id'] = results.get('run_id', 'latest')
    
    with t1:
        try:
            rmsd.render_rmsd_tab(results)
        except Exception as e:
            st.error(f"Error rendering Summary tab: {e}")
        
    with t2:
        try:
            sequence.render_sequences_tab(results)
        except Exception as e:
            st.error(f"Error rendering Sequence tab: {e}")
        
    with t3:
        try:
            phylo.render_phylo_tree_tab(results)
        except Exception as e:
            st.error(f"Error rendering Phylogeny tab: {e}")
        
    with t4:
        try:
            clusters.render_clusters_tab(results)
        except Exception as e:
            st.error(f"Error rendering Clusters tab: {e}")
        
    with t5:
        try:
            structure.render_3d_viewer_tab(results)
        except Exception as e:
            st.error(f"Error rendering 3D Viewer tab: {e}")
        
    with t6:
        try:
            ligand.render_ligand_tab(results)
        except Exception as e:
            st.error(f"Error rendering Ligand tab: {e}")
        
    with t7:
        try:
            comparison.render_comparison_tab(results)
        except Exception as e:
            st.error(f"Error rendering Comparison tab: {e}")
            
    with t8:
        try:
            downloads.render_downloads_tab(results)
        except Exception as e:
            st.error(f"Error rendering Downloads tab: {e}")

def render_compact_summary(results: Optional[Dict[str, Any]] = None) -> None:
    """
    Render a high-level summary of results for the dashboard.
    
    Args:
        results: Results dictionary. If None, retrieves from session state.
    """
    if results is None:
        results = st.session_state.get('results')
        
    if not results:
        return
        
    st.markdown("### 📊 Latest Analysis Summary")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    stats = results.get('stats', {})
    q_metrics = results.get('quality_metrics', {})
    
    with col1:
        st.metric("Total PDBs", len(results.get('pdb_ids', [])))
    with col2:
        st.metric("Mean RMSD", f"{stats.get('mean_rmsd', 0):.2f} Å")
    
    if q_metrics:
        avg_tm = sum(m['tm_score'] for m in q_metrics.values()) / len(q_metrics)
        avg_gdt = sum(m['gdt_ts'] for m in q_metrics.values()) / len(q_metrics)
        with col3:
            st.metric("Avg TM-Score", f"{avg_tm:.3f}")
        with col4:
            st.metric("Avg GDT-TS", f"{avg_gdt:.3f}")
    else:
        with col3:
             st.metric("Seq Identity", f"{stats.get('seq_identity', 0):.1f}%")
        with col4:
             st.metric("Coverage", "100%")
             
    with col5:
        st.metric("Seq Length", results.get('sequence_length', 'N/A'))
    
    if st.button("👁️ View Full Detailed Analysis", type="primary", use_container_width=True):
        st.session_state.active_tab = "Results"
        st.rerun()
