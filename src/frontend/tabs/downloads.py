import streamlit as st
from typing import Dict, Any
import zipfile
import io


@st.cache_data(max_entries=3, ttl=300, show_spinner=False)
def generate_zip_package(results: Dict[str, Any], run_id: str) -> bytes:
    """Generate and cache the complete package ZIP file bytes."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        # Add PDB alignment
        if results.get("alignment_pdb") and results["alignment_pdb"].exists():
            zip_file.write(results["alignment_pdb"], arcname=f"alignment_{run_id}.pdb")

        # Add AFasta
        if results.get("alignment_afasta") and results["alignment_afasta"].exists():
            zip_file.write(
                results["alignment_afasta"],
                arcname=f"alignment_{run_id}.afasta",
            )

        # Add RMSD CSV
        if results.get("rmsd_df") is not None:
            csv_data = results["rmsd_df"].to_csv()
            zip_file.writestr(f"rmsd_matrix_{run_id}.csv", csv_data)

        # Add Heatmap
        if results.get("heatmap_path") and results["heatmap_path"].exists():
            zip_file.write(
                results["heatmap_path"], arcname=f"rmsd_heatmap_{run_id}.png"
            )

        # Add Lab Notebook (if it exists or try to export)
        try:
            from src.backend.notebook_exporter import NotebookExporter

            exporter = NotebookExporter()
            nb_path = exporter.export(results)  # Generates if needed
            if nb_path and nb_path.exists():
                zip_file.write(nb_path, arcname=f"lab_notebook_{run_id}.html")
        except Exception:
            pass
    return zip_buffer.getvalue()


def _render_report_section_checkboxes() -> list:
    report_sections = []
    c1, c2 = st.columns(2)
    with c1:
        if st.checkbox("Summary & Stats", value=True):
            report_sections.append("summary")
        if st.checkbox("RMSD Heatmap", value=True):
            report_sections.append("heatmap")
    with c2:
        if st.checkbox("Sequence Alignment", value=True):
            report_sections.append("sequence")
        if st.checkbox("Phylogenetic Tree", value=True):
            report_sections.append("tree")
    return report_sections


def _render_pdf_report_generator(results: Dict[str, Any], run_id: str) -> None:
    st.markdown("### 📄 Analysis Report")
    st.write("Customize your report:")
    report_sections = _render_report_section_checkboxes()

    if not st.button(
        "🚀 Generate PDF Report", type="primary", use_container_width=True
    ):
        return
    with st.spinner("Generating PDF..."):
        try:
            pdf_path = st.session_state.report_generator.generate_full_report(
                results, sections=report_sections
            )
            if pdf_path and pdf_path.exists():
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        label="📥 Download PDF Report",
                        data=f,
                        file_name=f"Mustang_Report_{run_id}.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )
        except Exception as e:
            st.error(f"Failed to generate PDF: {e}")


def _render_lab_notebook_exporter(results: Dict[str, Any], run_id: str) -> None:
    st.divider()
    st.markdown("### 📒 Lab Notebook (HTML)")
    st.write("Generate a standalone HTML notebook with embedded 3D structures.")

    if not st.button("🧪 Export Lab Notebook", use_container_width=True):
        return
    with st.spinner("Exporting..."):
        try:
            from src.backend.notebook_exporter import NotebookExporter

            notebook_path = NotebookExporter().export(results)
            if notebook_path and notebook_path.exists():
                with open(notebook_path, "rb") as f:
                    st.download_button(
                        label="📥 Download HTML Notebook",
                        data=f,
                        file_name=f"Lab_Notebook_{run_id}.html",
                        mime="text/html",
                        use_container_width=True,
                    )
        except Exception as e:
            st.error(f"Failed to export notebook: {e}")


def _render_raw_files_column(results: Dict[str, Any], run_id: str) -> None:
    st.markdown("### 📊 Raw Data & Files")
    st.write("Download individual analysis files:")

    if results.get("rmsd_df") is not None:
        csv = results["rmsd_df"].to_csv().encode("utf-8")
        st.download_button(
            "📥 Raw RMSD Matrix (CSV)",
            csv,
            f"rmsd_matrix_{run_id}.csv",
            "text/csv",
            use_container_width=True,
        )

    if results.get("alignment_pdb") and results["alignment_pdb"].exists():
        with open(results["alignment_pdb"], "rb") as f:
            st.download_button(
                "📥 Mustang PDB Alignment",
                f,
                f"alignment_{run_id}.pdb",
                use_container_width=True,
            )

    if results.get("alignment_afasta") and results["alignment_afasta"].exists():
        with open(results["alignment_afasta"], "rb") as f:
            st.download_button(
                "📥 Sequence Alignment (FASTA)",
                f,
                f"alignment_{run_id}.fasta",
                use_container_width=True,
            )

    if results.get("heatmap_path") and results["heatmap_path"].exists():
        with open(results["heatmap_path"], "rb") as f:
            st.download_button(
                "📥 RMSD Heatmap (PNG)",
                f,
                f"heatmap_{run_id}.png",
                "image/png",
                use_container_width=True,
            )


def _render_complete_package_download(results: Dict[str, Any], run_id: str) -> None:
    st.divider()
    st.markdown("### 📦 Complete Package")
    st.write(
        "Download all results, alignments, and the lab notebook in a single compressed ZIP file."
    )
    zip_data = generate_zip_package(results, run_id)
    st.download_button(
        label="📥 Download Everything (.zip)",
        data=zip_data,
        file_name=f"Mustang_Full_Results_{run_id}.zip",
        mime="application/zip",
        use_container_width=True,
        type="primary",
    )


def render_downloads_tab(results: Dict[str, Any]) -> None:
    """
    Render the Data Downloads tab.

    Args:
        results: The results dictionary containing paths to all exportable artifacts.
    """
    st.subheader("Data Downloads")

    # Defensive metadata retrieval
    run_id = results.get("id") or results.get("run_id") or "latest"

    col_d1, col_d2 = st.columns(2)
    with col_d1:
        _render_pdf_report_generator(results, run_id)
        _render_lab_notebook_exporter(results, run_id)
    with col_d2:
        _render_raw_files_column(results, run_id)

    _render_complete_package_download(results, run_id)
