import streamlit as st

def render_hero_section():
    """Render the main landing page / hero section."""
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
