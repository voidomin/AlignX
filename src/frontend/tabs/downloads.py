import streamlit as st
from typing import Dict, Any

def render_downloads_tab(results: Dict[str, Any]) -> None:
    """
    Render the Data Downloads tab.
    
    Args:
        results: The results dictionary containing paths to all exportable artifacts.
    """
    st.subheader("Data Downloads")
    
    col_d1, col_d2 = st.columns(2)
    
    with col_d1:
        st.markdown("### 📄 Analysis Report")
        st.write("Customize your report:")
        
        report_sections = []
        c1, c2 = st.columns(2)
        with c1:
            if st.checkbox("Summary & Stats", value=True): report_sections.append("summary")
            if st.checkbox("RMSD Heatmap", value=True): report_sections.append("heatmap")
        with c2:
            if st.checkbox("Sequence Alignment", value=True): report_sections.append("sequence")
            if st.checkbox("Phylogenetic Tree", value=True): report_sections.append("tree")
        
        if st.button("🚀 Generate PDF Report", type="primary", use_container_width=True):
            with st.spinner("Generating PDF..."):
                try:
                    pdf_path = st.session_state.report_generator.generate_full_report(results, sections=report_sections)
                    if pdf_path and pdf_path.exists():
                        with open(pdf_path, "rb") as f:
                            st.download_button(
                                label="📥 Download PDF Report",
                                data=f,
                                file_name=f"Mustang_Report_{results['id']}.pdf",
                                mime="application/pdf",
                                use_container_width=True
                            )
                except Exception as e:
                    st.error(f"Failed to generate PDF: {e}")

        st.divider()
        st.markdown("### 📒 Lab Notebook (HTML)")
        st.write("Generate a standalone HTML notebook with embedded 3D structures.")
        
        if st.button("🧪 Export Lab Notebook", use_container_width=True):
            with st.spinner("Exporting..."):
                try:
                    from src.backend.notebook_exporter import NotebookExporter
                    exporter = NotebookExporter()
                    notebook_path = exporter.export(results)
                    
                    if notebook_path and notebook_path.exists():
                        with open(notebook_path, "rb") as f:
                            st.download_button(
                                label="📥 Download HTML Notebook",
                                data=f,
                                file_name=f"Lab_Notebook_{results['id']}.html",
                                mime="text/html",
                                use_container_width=True
                            )
                except Exception as e:
                    st.error(f"Failed to export notebook: {e}")

    with col_d2:
        st.markdown("### 📊 Raw Data & Files")
        
        st.write("Download individual analysis files:")
        
        # CSV Data
        if results.get('rmsd_df') is not None:
             csv = results['rmsd_df'].to_csv().encode('utf-8')
             st.download_button("📥 Raw RMSD Matrix (CSV)", csv, f"rmsd_matrix_{results['id']}.csv", "text/csv", use_container_width=True)
        
        # Mustang Alignment
        if results.get('alignment_pdb') and results['alignment_pdb'].exists():
            with open(results['alignment_pdb'], "rb") as f:
                st.download_button("📥 Mustang PDB Alignment", f, f"alignment_{results['id']}.pdb", use_container_width=True)
                
        # Fasta Alignment
        if results.get('alignment_afasta') and results['alignment_afasta'].exists():
            with open(results['alignment_afasta'], "rb") as f:
                st.download_button("📥 Sequence Alignment (FASTA)", f, f"alignment_{results['id']}.fasta", use_container_width=True)
        
        # RMSD Plot
        if results.get('heatmap_path') and results['heatmap_path'].exists():
            with open(results['heatmap_path'], "rb") as f:
                st.download_button("📥 RMSD Heatmap (PNG)", f, f"heatmap_{results['id']}.png", "image/png", use_container_width=True)
