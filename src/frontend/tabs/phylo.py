import streamlit as st
from src.frontend.tabs.common import render_learning_card, render_help_expander

from typing import Dict, Any

def render_phylo_tree_tab(results: Dict[str, Any]) -> None:
    """
    Render the Phylogenetic Tree tab.
    
    Args:
        results: The results dictionary containing tree visualization data.
    """
    st.subheader("🌳 Phylogenetic Tree (UPGMA)")
    render_learning_card("Tree")
    render_help_expander("tree")
        
    if results.get('tree_fig'):
        st.plotly_chart(results['tree_fig'], use_container_width=True)
    elif results.get('tree_path') and results['tree_path'].exists():
        st.image(str(results['tree_path']), use_container_width=True)
    else:
        st.warning("Phylogenetic tree not available")
