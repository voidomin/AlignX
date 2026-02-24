import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from src.frontend.tabs.common import render_learning_card, render_help_expander

from typing import Dict, Any

def render_phylo_tree_tab(results: Dict[str, Any]) -> None:
    """
    Render the Phylogenetic Tree tab.
    
    Args:
        results: The results dictionary containing tree visualization data.
    """
    st.subheader("🌳 Structural Tree & Quality Validation")
    render_learning_card("Tree")
    render_help_expander("tree")
    
    col_tree, col_ram = st.columns([1.2, 1])
         
    with col_tree:
        st.markdown("#### Evolutionary Relationship (UPGMA)")
        if results.get('tree_fig'):
            st.plotly_chart(results['tree_fig'], use_container_width=True)
        elif results.get('tree_path') and results['tree_path'].exists():
            st.image(str(results['tree_path']), use_container_width=True)
        else:
            st.warning("Phylogenetic tree not available")

    with col_ram:
        st.markdown("#### Ramachandran Structural Validation")
        torsion_data = results.get('torsion_data')
        
        if torsion_data:
            # Combine all chain data for the plot
            all_data = pd.concat(torsion_data.values(), keys=torsion_data.keys()).reset_index(level=0).rename(columns={'level_0': 'chain'})
            
            # Create interactive plot
            fig = px.scatter(
                all_data, 
                x="phi", y="psi", 
                color="region",
                symbol="chain",
                hover_data=["residue_name", "residue_id"],
                title="Torsion Angle Distribution",
                labels={"phi": "Phi (φ)", "psi": "Psi (ψ)"},
                template="plotly_white",
                color_discrete_map={
                    "Favored (Alpha)": "#4CAF50",
                    "Favored (Beta)": "#2196F3", 
                    "Favored (L-Alpha)": "#8BC34A",
                    "Allowed": "#FFC107",
                    "Outlier": "#F44336"
                }
            )
            
            # Add axis lines for 0
            fig.add_hline(y=0, line_dash="dash", line_color="rgba(0,0,0,0.2)")
            fig.add_vline(x=0, line_dash="dash", line_color="rgba(0,0,0,0.2)")
            
            # Set ranges
            fig.update_xaxes(range=[-180, 180])
            fig.update_yaxes(range=[-180, 180])
            
            fig.update_layout(height=450, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("💡 Ramachandran analysis is currently computing or not available for this run.")

    # Summary Metrics
    if results.get('ramachandran_stats'):
        st.divider()
        stats = results['ramachandran_stats']
        m1, m2, m3 = st.columns(3)
        
        with m1:
            st.metric("Favored Region %", f"{stats['favored_percent']:.1f}%", help="Higher is better. Typically >90% for high-resolution structures.")
        with m2:
            st.metric("Total Outliers", stats['outlier_count'])
        with m3:
            st.metric("Validated Residues", stats['total_residues'])
            
        if stats['outliers_list']:
            with st.expander("🚩 List of Structural Outliers (Top 10)"):
                st.write(", ".join(stats['outliers_list']))
    elif not torsion_data:
        st.warning("Torsion statistics not available")
