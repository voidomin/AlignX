import streamlit as st
import pandas as pd
import numpy as np
from src.frontend.tabs.common import render_help_expander

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
                member_data = []
                for m in members:
                    title = st.session_state.metadata.get(m, {}).get('title', 'Unknown Title') if hasattr(st.session_state, 'metadata') else 'N/A'
                    member_data.append({"PDB ID": m, "Description": title})
                
                st.table(pd.DataFrame(member_data))
                
                # View in 3D Button
                if st.button(f"🎯 View Cluster {cid} in 3D", key=f"btn_view_cluster_{cid}", use_container_width=True):
                    st.session_state.selected_cluster_members = members
                    st.session_state.show_3d_viewer = True 
                    st.success(f"Filter applied for Cluster {cid}. Switch to '3D Visualization' tab to view.")
    else:
        st.info("No clusters identified with current settings.")
