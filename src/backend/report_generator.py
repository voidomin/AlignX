"""
Report Generator Module.
Generates comprehensive PDF reports for Mustang analysis results.
"""

from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime
import pandas as pd
from fpdf import FPDF
from ..utils.logger import get_logger

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

    def generate_report(self, results: Dict[str, Any], pdb_ids: List[str]) -> Path:
        """
        Generate PDF report from analysis results.
        
        Args:
            results: Dictionary containing analysis results (rmsd_df, stats, images, etc.)
            pdb_ids: List of PDB IDs analyzed
            
        Returns:
            Path to generated PDF
        """
        try:
            pdf = PDFReport()
            pdf.add_page()
            
            # Title Section
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(0, 10, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}", 0, 1)
            pdf.ln(5)
            
            # 1. Input Summary
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(0, 10, "1. Analysis Summary", 0, 1)
            pdf.set_font("Arial", '', 11)
            pdf.multi_cell(0, 7, f"Analyzed {len(pdb_ids)} structures: {', '.join(pdb_ids)}")
            
            stats = results.get('stats', {})
            if stats:
                pdf.ln(5)
                pdf.set_font("Arial", 'B', 10)
                pdf.cell(40, 7, "RMSD Statistics:", 0, 1)
                pdf.set_font("Arial", '', 10)
                pdf.cell(50, 7, f"Mean RMSD: {stats.get('mean_rmsd', 0):.2f} A", 0, 1)
                pdf.cell(50, 7, f"Median RMSD: {stats.get('median_rmsd', 0):.2f} A", 0, 1)
                pdf.cell(50, 7, f"Min/Max RMSD: {stats.get('min_rmsd', 0):.2f} / {stats.get('max_rmsd', 0):.2f} A", 0, 1)
            
            pdf.ln(10)
            
            # 2. RMSD Heatmap
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(0, 10, "2. RMSD Heatmap", 0, 1)
            
            heatmap_path = results.get('heatmap_path')
            if heatmap_path and heatmap_path.exists():
                # Fit image to width
                pdf.image(str(heatmap_path), x=10, w=190)
            else:
                pdf.set_font("Arial", 'I', 10)
                pdf.cell(0, 10, "Heatmap image not available", 0, 1)
            
            pdf.add_page()
            
            # 3. Phylogenetic Tree
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(0, 10, "3. Structural Phylogenetic Tree", 0, 1)
            
            tree_path = results.get('tree_path')
            if tree_path and tree_path.exists():
                 pdf.image(str(tree_path), x=10, w=190)
            else:
                 pdf.cell(0, 10, "Tree image not available", 0, 1)

            pdf.ln(10)

             # 4. Pairwise RMSD Matrix (Top results)
            pdf.set_font("Arial", 'B', 14)
            pdf.cell(0, 10, "4. Pairwise RMSD Matrix (Snippet)", 0, 1)
            
            rmsd_df = results.get('rmsd_df')
            if rmsd_df is not None:
                pdf.set_font("Courier", '', 8)
                # Convert first few rows to string format
                matrix_str = rmsd_df.head(10).to_string()
                pdf.multi_cell(0, 5, matrix_str)
            
            # Footer / Output
            pdf.output(str(self.report_path))
            logger.info(f"Report generated at {self.report_path}")
            
            return self.report_path

        except Exception as e:
            logger.error(f"Failed to generate report: {e}")
            raise e
