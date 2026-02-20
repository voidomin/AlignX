"""
Report Generator Module.
Generates comprehensive PDF reports for Mustang analysis results.
"""

from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import pandas as pd
from fpdf import FPDF
from src.utils.logger import get_logger

logger = get_logger()

class PDFReport(FPDF):
    def header(self):
        # Logo or Title
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Mustang Structural Alignment Report', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

class ReportGenerator:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.report_path = output_dir / f"mustang_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    def generate_full_report(self, results: Dict[str, Any], pdb_ids: List[str] = None, sections: List[str] = None) -> Path:
        """
        Generate PDF report from analysis results.
        
        Args:
            results: Dictionary containing analysis results
            pdb_ids: List of PDB IDs analyzed (default: from results)
            sections: List of sections to include (default: all)
        """
        if pdb_ids is None:
            pdb_ids = results.get('pdb_ids', [])
            
        if sections is None:
            sections = ["summary", "insights", "heatmap", "tree", "matrix"]
            
        try:
            pdf = PDFReport()
            pdf.add_page()
            
            # Helper to clean text for FPDF (Latin-1)
            def clean_text(text):
                if not isinstance(text, str): return str(text)
                return text.encode('latin-1', 'replace').decode('latin-1')

            # Title Section (Always included)
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", 0, 1)
            pdf.ln(5)
            
            # 1. Input Summary
            if "summary" in sections:
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(0, 10, clean_text("1. Analysis Summary"), 0, 1)
                pdf.set_font("Arial", '', 11)
                pdf.multi_cell(0, 7, clean_text(f"Analyzed {len(pdb_ids)} structures: {', '.join(pdb_ids)}"))
                
                stats = results.get('stats', {})
                if stats:
                    pdf.ln(5)
                    pdf.set_font("Arial", 'B', 10)
                    pdf.cell(40, 7, clean_text("RMSD Statistics:"), 0, 1)
                    pdf.set_font("Arial", '', 10)
                    pdf.cell(50, 7, clean_text(f"Mean RMSD: {stats.get('mean_rmsd', 0):.2f} A"), 0, 1)
                    pdf.cell(50, 7, clean_text(f"Median RMSD: {stats.get('median_rmsd', 0):.2f} A"), 0, 1)
                    pdf.cell(50, 7, clean_text(f"Min/Max RMSD: {stats.get('min_rmsd', 0):.2f} / {stats.get('max_rmsd', 0):.2f} A"), 0, 1)
                pdf.ln(5)
            
            # 2. Automated Insights (Key Findings)
            if "insights" in sections:
                from src.backend.insights import InsightsGenerator
                gen = InsightsGenerator({})
                insights = gen.generate_insights(results)
                
                if insights:
                    pdf.set_font("Arial", 'B', 14)
                    pdf.cell(0, 10, clean_text("Key Findings"), 0, 1)
                    pdf.set_font("Arial", '', 11)
                    for item in insights:
                        # Remove markdown bold/code and clean encoding
                        clean_item = item.replace('**', '').replace('`', '')
                        pdf.multi_cell(0, 6, clean_text(f"- {clean_item}"))
                    pdf.ln(5)
            
            # 3. RMSD Heatmap
            if "heatmap" in sections:
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(0, 10, clean_text("RMSD Heatmap"), 0, 1)
                
                heatmap_path = results.get('heatmap_path')
                if heatmap_path and heatmap_path.exists():
                    try:
                        pdf.image(str(heatmap_path), x=10, w=190)
                    except Exception as img_err:
                         pdf.cell(0, 10, clean_text(f"Error loading image: {img_err}"), 0, 1)
                else:
                    pdf.set_font("Arial", 'I', 10)
                    pdf.cell(0, 10, clean_text("Heatmap image not available"), 0, 1)
                pdf.add_page()
            
            # 4. Phylogenetic Tree
            if "tree" in sections:
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(0, 10, clean_text("Structural Phylogenetic Tree"), 0, 1)
                
                tree_path = results.get('tree_path')
                if tree_path and tree_path.exists():
                     try:
                        pdf.image(str(tree_path), x=10, w=190)
                     except Exception as img_err:
                        pdf.cell(0, 10, clean_text(f"Error loading image: {img_err}"), 0, 1)
                else:
                     pdf.cell(0, 10, clean_text("Tree image not available"), 0, 1)
                pdf.ln(10)

             # 5. Pairwise RMSD Matrix (Top results)
            if "matrix" in sections:
                pdf.set_font("Arial", 'B', 14)
                pdf.cell(0, 10, clean_text("Pairwise RMSD Matrix (Snippet)"), 0, 1)
                
                rmsd_df = results.get('rmsd_df')
                if rmsd_df is not None:
                    pdf.set_font("Courier", '', 8)
                    matrix_str = rmsd_df.head(10).to_string()
                    pdf.multi_cell(0, 5, clean_text(matrix_str))
            
            # Footer / Output
            pdf.output(str(self.report_path))
            logger.info(f"Report generated at {self.report_path}")
            
            return self.report_path

        except Exception as e:
            logger.error(f"Failed to generate report: {e}")
            raise e
