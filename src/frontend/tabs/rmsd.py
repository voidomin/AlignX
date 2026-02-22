import streamlit as st
import pandas as pd
import plotly.express as px
from src.frontend.tabs.common import render_learning_card, render_help_expander

from typing import Dict, Any

def render_rmsd_tab(results: Dict[str, Any]) -> None:
    """
    Render the RMSD Analysis tab.
    
    Args:
        results: The results dictionary containing RMSD data and stats.
    """
    st.subheader("📊 RMSD & Alignment Quality")
    render_learning_card("Summary")
    
    # Automated Insights — regenerate when results change (keyed by run ID)
    current_run_id = results.get('id', 'unknown')
    if st.session_state.get('insights_run_id') != current_run_id:
        from src.backend.insights import InsightsGenerator
        gen = InsightsGenerator(st.session_state.config)
        st.session_state.insights = gen.generate_insights(results)
        st.session_state.insights_run_id = current_run_id
    
    if st.session_state.get('insights'):
        with st.expander("🧠 Automated Insights (Smart Findings)", expanded=True):
            for insight in st.session_state.insights:
                st.markdown(insight)
    
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
    colormap = st.session_state.config.get('visualization', {}).get('heatmap_colormap', 'RdYlBu_r')
    st.dataframe(results['rmsd_df'].style.background_gradient(cmap=colormap))
    
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
