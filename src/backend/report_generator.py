"""
Report Generator Module.
Generates comprehensive PDF reports for Mustang analysis results.
"""

from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
from fpdf import FPDF
from src.utils.logger import get_logger

logger = get_logger()


class PDFReport(FPDF):
    def header(self):
        # Logo or Title
        self.set_font("Arial", "B", 15)
        self.cell(0, 10, "Mustang Structural Alignment Report", 0, 1, "C")
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Arial", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", 0, 0, "C")


def _clean_text(text: Any) -> str:
    """FPDF's classic core fonts are Latin-1 only; map the structural
    biology symbols we actually emit (Å) and drop anything else FPDF can't
    encode rather than letting it raise."""
    if not isinstance(text, str):
        return str(text)
    # Å (Angstrom) is \xc5 in Latin-1
    text = text.replace("Å", chr(197))
    try:
        return text.encode("latin-1", "replace").decode("latin-1")
    except Exception:
        return "".join(c for c in text if ord(c) < 128)


class ReportGenerator:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.report_path = (
            output_dir
            / f"mustang_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )

    @staticmethod
    def _write_summary_section(
        pdf: FPDF, results: Dict[str, Any], pdb_ids: List[str]
    ) -> None:
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, _clean_text("1. Analysis Summary"), 0, 1)
        pdf.set_font("Arial", "", 11)
        pdf.multi_cell(
            0,
            7,
            _clean_text(f"Analyzed {len(pdb_ids)} structures: {', '.join(pdb_ids)}"),
        )

        stats = results.get("stats", {})
        if stats:
            pdf.ln(5)
            pdf.set_font("Arial", "B", 10)
            pdf.cell(40, 7, _clean_text("RMSD Statistics:"), 0, 1)
            pdf.set_font("Arial", "", 10)
            pdf.cell(
                50,
                7,
                _clean_text(f"Mean RMSD: {stats.get('mean_rmsd', 0):.2f} Å"),
                0,
                1,
            )
            pdf.cell(
                50,
                7,
                _clean_text(f"Median RMSD: {stats.get('median_rmsd', 0):.2f} Å"),
                0,
                1,
            )
            pdf.cell(
                50,
                7,
                _clean_text(
                    f"Min/Max RMSD: {stats.get('min_rmsd', 0):.2f} / {stats.get('max_rmsd', 0):.2f} Å"
                ),
                0,
                1,
            )
        pdf.ln(5)

    @staticmethod
    def _write_insights_section(pdf: FPDF, results: Dict[str, Any]) -> None:
        # Reuse insights already computed (and persisted) during the
        # original pipeline run when available. Regenerating here requires
        # results["rmsd_df"] to be a live pandas DataFrame, which it no
        # longer is once a run's metadata has been through
        # sanitize_for_json and reloaded from history.
        insights = results.get("insights")
        if insights is None:
            from src.backend.insights import InsightsGenerator

            insights = InsightsGenerator({}).generate_insights(results)
        if not insights:
            return

        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, _clean_text("Key Findings"), 0, 1)
        pdf.set_font("Arial", "", 11)
        from src.backend.insights import InsightsGenerator

        for item in insights:
            # Remove the icon marker, markdown bold/code, and clean encoding
            clean_item = (
                InsightsGenerator.strip_icon_marker(item)
                .replace("**", "")
                .replace("`", "")
            )
            pdf.multi_cell(0, 6, _clean_text(f"- {clean_item}"))
        pdf.ln(5)

    @staticmethod
    def _write_image_section(
        pdf: FPDF,
        title: str,
        image_path,
        missing_text: str,
        missing_font: tuple,
        after: str,
    ) -> None:
        """Shared rendering for the heatmap/tree sections - a title, the
        image if it exists (falling back to an inline error message if
        FPDF can't load it), or a placeholder message in `missing_font` if
        it doesn't (the two sections use different fonts for that message,
        preserved as-is rather than unified)."""
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, _clean_text(title), 0, 1)

        if image_path and image_path.exists():
            try:
                pdf.image(str(image_path), x=10, w=190)
            except Exception as img_err:
                pdf.cell(0, 10, _clean_text(f"Error loading image: {img_err}"), 0, 1)
        else:
            pdf.set_font(*missing_font)
            pdf.cell(0, 10, _clean_text(missing_text), 0, 1)

        if after == "page":
            pdf.add_page()
        else:
            pdf.ln(10)

    @staticmethod
    def _write_matrix_section(pdf: FPDF, results: Dict[str, Any]) -> None:
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, _clean_text("Pairwise RMSD Matrix (Snippet)"), 0, 1)

        rmsd_df = results.get("rmsd_df")
        if rmsd_df is not None:
            pdf.set_font("Courier", "", 8)
            pdf.multi_cell(0, 5, _clean_text(rmsd_df.head(10).to_string()))

    def generate_full_report(
        self,
        results: Dict[str, Any],
        pdb_ids: List[str] = None,
        sections: List[str] = None,
    ) -> Path:
        """
        Generate PDF report from analysis results.

        Args:
            results: Dictionary containing analysis results
            pdb_ids: List of PDB IDs analyzed (default: from results)
            sections: List of sections to include (default: all)
        """
        if pdb_ids is None:
            pdb_ids = results.get("pdb_ids", [])
        if sections is None:
            sections = ["summary", "insights", "heatmap", "tree", "matrix"]

        try:
            pdf = PDFReport()
            pdf.add_page()

            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", 0, 1)
            pdf.ln(5)

            if "summary" in sections:
                self._write_summary_section(pdf, results, pdb_ids)
            if "insights" in sections:
                self._write_insights_section(pdf, results)
            if "heatmap" in sections:
                self._write_image_section(
                    pdf,
                    "RMSD Heatmap",
                    results.get("heatmap_path"),
                    "Heatmap image not available",
                    missing_font=("Arial", "I", 10),
                    after="page",
                )
            if "tree" in sections:
                self._write_image_section(
                    pdf,
                    "Structural Phylogenetic Tree",
                    results.get("tree_path"),
                    "Tree image not available",
                    missing_font=("Arial", "B", 14),
                    after="ln",
                )
            if "matrix" in sections:
                self._write_matrix_section(pdf, results)

            pdf.output(str(self.report_path))
            logger.info(f"Report generated at {self.report_path}")
            return self.report_path

        except Exception as e:
            logger.exception("Failed to generate report")
            raise e
