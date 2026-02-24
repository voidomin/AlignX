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
         
    st.markdown("#### 1. Evolutionary Relationship (UPGMA)")
    if results.get('tree_fig'):
        st.plotly_chart(results['tree_fig'], use_container_width=True)
    elif results.get('tree_path') and results['tree_path'].exists():
        st.image(str(results['tree_path']), use_container_width=True)
    else:
        st.warning("Phylogenetic tree not available")

    st.divider()
    st.markdown("#### 2. Ramachandran Structural Validation")
    
    torsion_data = results.get('torsion_data')
    pdb_ids = results.get('pdb_ids', [])
    
    if torsion_data:
        # Create a mapping from Chain ID (A, B, C...) to Protein Name
        # Mustang assigns chains in the order of inputs
        chain_map = {}
        for i, pid in enumerate(pdb_ids):
            chain_id = chr(65 + i) # 0->A, 1->B...
            chain_map[chain_id] = pid

        # Combine all chain data and map names
        all_data = pd.concat(torsion_data.values(), keys=torsion_data.keys()).reset_index(level=0).rename(columns={'level_0': 'chain'})
        all_data['protein_name'] = all_data['chain'].map(chain_map).fillna(all_data['chain'])
        
        protein_names = sorted(all_data['protein_name'].unique())

        col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([2, 1, 1])
        with col_ctrl1:
            selected_proteins = st.multiselect(
                "🎯 Highlight Specific Proteins",
                options=protein_names,
                default=[],
                help="Select proteins to highlight them on the plot. Others will be dimmed."
            )
        with col_ctrl2:
            st.write("") # Spacer
            show_all = st.toggle("Show Residue Labels", value=False, help="Display residue names (e.g. GLY35) directly on the plot.")
        with col_ctrl3:
            st.write("") # Spacer
            show_regions = st.toggle("Show Regions", value=True, help="Display shaded reference regions for Alpha-Helices and Beta-Sheets.")

        # Dynamic Opacity & Size
        all_data['opacity'] = 1.0
        all_data['size'] = 8
        if selected_proteins:
            all_data['opacity'] = all_data['protein_name'].apply(lambda x: 1.0 if x in selected_proteins else 0.15)
            all_data['size'] = all_data['protein_name'].apply(lambda x: 12 if x in selected_proteins else 6)

        # Create interactive plot
        fig = go.Figure()

        # 1. Add Background Regions (Rectangles as a proxy for shaded areas)
        if show_regions:
            # Favored Alpha (The "Green Region")
            fig.add_vrect(x0=-100, x1=-30, y0=-80, y1=20, fillcolor="rgba(76, 175, 80, 0.08)", line_width=0, layer="below", annotation_text="Alpha-Helix", annotation_position="bottom left")
            # Favored Beta (The "Blue Region")
            fig.add_vrect(x0=-160, x1=-50, y0=90, y1=180, fillcolor="rgba(33, 150, 243, 0.08)", line_width=0, layer="below", annotation_text="Beta-Sheet", annotation_position="top left")
        
        # 2. Add Data Trace
        for region in all_data['region'].unique():
            reg_data = all_data[all_data['region'] == region]
            color_map = {
                "Favored (Alpha)": "#4CAF50",
                "Favored (Beta)": "#2196F3", 
                "Favored (L-Alpha)": "#8BC34A",
                "Allowed": "#FFC107",
                "Outlier": "#F44336",
                "Terminal": "#9E9E9E"
            }
            
            fig.add_trace(go.Scatter(
                x=reg_data['phi'],
                y=reg_data['psi'],
                mode='markers+text' if show_all else 'markers',
                name=region,
                marker=dict(
                    color=color_map.get(region, "#9E9E9E"),
                    opacity=reg_data['opacity'],
                    size=reg_data['size'],
                    line=dict(width=1, color='rgba(255,255,255,0.3)')
                ),
                text=reg_data['residue_name'] + reg_data['residue_id'].astype(str),
                textposition="top center",
                textfont=dict(size=9, color='white'),
                customdata=reg_data[['protein_name', 'residue_name', 'residue_id', 'phi', 'psi']],
                hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}%{customdata[2]}<br>φ: %{customdata[3]:.1f}, ψ: %{customdata[4]:.1f}<extra></extra>"
            ))

        # Add axis lines for 0
        fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.1)")
        fig.add_vline(x=0, line_dash="dash", line_color="rgba(255,255,255,0.1)")
        
        fig.update_layout(
            template="plotly_dark",
            xaxis_title="Phi (φ)",
            yaxis_title="Psi (ψ)",
            xaxis=dict(range=[-180, 180], gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(range=[-180, 180], gridcolor="rgba(255,255,255,0.05)"),
            height=600,
            margin=dict(t=30, b=50, l=40, r=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            hoverlabel=dict(bgcolor="#1E1E1E", font_size=12, font_family="monospace")
        )
        
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
