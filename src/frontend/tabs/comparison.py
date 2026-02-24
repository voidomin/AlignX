"""
Batch comparison tab for comparing multiple Mustang runs.
"""

import streamlit as st
from pathlib import Path
import plotly.express as px
import pandas as pd
from src.backend.result_manager import ResultManager

def render_comparison_tab(current_results: dict):
    """
    Render comparative analysis between runs.
    """
    st.header("🔄 Batch Comparison Mode")
    
    with st.expander("ℹ️ About Batch Comparison", expanded=True):
        st.markdown("""
        **Batch Comparison** acts as a 'Structural Diff' tool for your pipeline. It allows you to mathematically compare 
        the structural relationships (RMSD matrices) between two different analysis runs.
        
        ### 🎯 Why use this?
        *   **Sensitivity Analysis**: See how adding or removing a specific protein member shifts the entire family's alignment.
        *   **Parameter Tuning**: Compare how different cleaning settings (water removal, heteroatom filtering) impact structural precision.
        *   **Subunit Bias**: Visualize the structural shift when swapping between different chains (e.g., Chain A vs Chain B) of the same protein.
        *   **Reproducibility**: Quickly verify that two identical runs produce the exact same consensus result.
        """)
    
    st.divider()

    # Initialize manager
    results_dir = Path("results")
    manager = ResultManager(results_dir)
    
    # List all runs
    all_runs = manager.list_runs()
    
    if len(all_runs) < 2:
        st.warning("Not enough past runs found for comparison. You need at least two sets of results.")
        return

    # Filter out current run from options
    current_id = current_results.get('id')
    other_runs = [r for r in all_runs if r['id'] != current_id]
    
    if not other_runs:
        st.warning("No other past runs found for comparison.")
        return

    # Selection UI
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Reference Run (Current)")
        st.code(f"ID: {current_id}\nProteins: {len(current_results.get('pdb_ids', []))}")
        
    with col2:
        st.subheader("Comparison Target")
        options = {f"{r['timestamp']} - {r['id'][:8]}... ({r['protein_count']} p)": r['id'] for r in other_runs}
        selected_display = st.selectbox("Select run to compare against:", options=list(options.keys()))
        target_id = options[selected_display]

    if st.button("🚀 Run Comparative Analysis", type="primary"):
        with st.spinner("Calculating differences..."):
            diff_df = manager.calculate_difference(current_id, target_id)
            
            if diff_df is None:
                st.error("No overlapping proteins found between these runs. Batch comparison requires at least one common protein (with the same name and chain selection) to calculate structural shifts.")
                return

            # Display results
            st.divider()
            st.subheader("📊 RMSD Difference Matrix (∆RMSD)")
            st.markdown("Positive values (red) indicate increased divergence in the current run compared to the target.")

            # Get colormap from config
            cmap = st.session_state.config.get('visualization', {}).get('heatmap_colormap', 'RdBu_r')
            
            fig = px.imshow(
                diff_df,
                labels=dict(x="Protein", y="Protein", color="Diff (Å)"),
                color_continuous_scale=cmap,
                aspect="auto",
                title=f"RMSD Delta (Inner Join): {current_id[:12]}... (Current) vs {target_id[:12]}... (Target)"
            )
            st.plotly_chart(fig, use_container_width=True)
            
            if diff_df.values.max() == 0 and diff_df.values.min() == 0:
                st.success("✨ **Perfect Consensus**: The structural relationships between the overlapping proteins are identical in both runs.")

            # Statistics Comparison
            st.subheader("📉 Statistics Comparison")
            target_rmsd = manager.get_run_rmsd(target_id)
            curr_rmsd = manager.get_run_rmsd(current_id)
            
            c1, c2, c3 = st.columns(3)
            with c1:
                diff_mean = curr_rmsd.values.mean() - target_rmsd.values.mean()
                st.metric("Mean RMSD Shift", f"{diff_mean:.3f} Å", delta=f"{diff_mean:.3f}", delta_color="inverse")
            with c2:
                st.metric("Current Mean", f"{curr_rmsd.values.mean():.3f} Å")
            with c3:
                st.metric("Target Mean", f"{target_rmsd.values.mean():.3f} Å")

            # 3D Comparison Placeholder
            st.divider()
            st.subheader("🔮 Structural Superposition Comparison")
            st.info("Side-by-side 3D viewing with camera syncing is coming in the next update!")
