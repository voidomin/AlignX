import logging

import pandas as pd
import plotly.io as pio
from pathlib import Path
from datetime import datetime
from jinja2 import Template

logger = logging.getLogger(__name__)


class NotebookExporter:
    """
    Generates a standalone HTML Lab Notebook from analysis results.
    """

    def __init__(self):
        self.template_path = (
            Path(__file__).parent.parent
            / "resources"
            / "templates"
            / "notebook_template.html"
        )
        self._template_str = None

    @property
    def template_str(self):
        if self._template_str is None:
            if self.template_path.exists():
                with open(self.template_path, "r", encoding="utf-8") as f:
                    self._template_str = f.read()
            else:
                # Fallback to minimal template if file is missing
                self._template_str = "<html><body><h1>Analysis Report</h1>{{ heatmap_div | safe }}</body></html>"
        return self._template_str

    def export(self, results, insights=None):
        """
        Generate HTML notebook from results.

        Args:
            results (dict): Pipeline results dictionary.
            insights (list, optional): List of insight strings.

        Returns:
            Path: Path to the generated HTML file.
        """
        try:
            # Prepare Data

            # CRITICAL: Create a copy to avoid mutating the global 'results' dict
            # which would break the dashboard (results.py) that expects floats
            stats = results.get("stats", {}).copy()
            # Format Mean RMSD nicely
            if "mean_rmsd" in stats and isinstance(stats["mean_rmsd"], (int, float)):
                stats["mean_rmsd"] = f"{stats['mean_rmsd']:.3f}"
            else:
                # If it's already a string or missing, leave it or set default
                if "mean_rmsd" not in stats:
                    stats["mean_rmsd"] = "N/A"

            # Populate missing stats
            if "num_structures" not in stats:
                stats["num_structures"] = len(results.get("rmsd_df", []))

            # Identity might be missing if sequence analysis wasn't run or failed
            if "identity" not in stats:
                stats["identity"] = stats.get("seq_identity", "N/A")

            # Chain/Alignment Length
            if "chain_length" not in stats:
                # Try to infer from alignment fasta or sequences if available
                stats["chain_length"] = "N/A"

            # PDB Content for 3D Viewer
            pdb_content = ""
            if results.get("alignment_pdb") and results["alignment_pdb"].exists():
                with open(results["alignment_pdb"], "r") as f:
                    content = f.read()
                    # Escape backticks to prevent JS template literal errors
                    pdb_content = content.replace("`", "\\`")

            # Load 3Dmol JS from local resource if available
            dmol_js = None
            try:
                js_path = Path(__file__).parent / "resources" / "3Dmol-min.js"
                if js_path.exists():
                    with open(js_path, "r", encoding="utf-8") as f:
                        dmol_js = f.read()
            except Exception as e:
                logger.warning(f"Could not load local 3Dmol.js: {e}")

            # 1. Heatmap
            heatmap_fig = results.get("heatmap_fig")
            # Embed plotly.js to solve "empty" (CDN) issue by using include_plotlyjs=True
            heatmap_div = (
                pio.to_html(heatmap_fig, full_html=False, include_plotlyjs=True)
                if heatmap_fig
                else "<p>No Heatmap Available</p>"
            )

            # 2. RMSF (Create fig if only data is present)
            rmsf_div = ""
            if results.get("rmsf_values"):
                import plotly.express as px

                rmsf_data = pd.DataFrame(
                    {
                        "Residue Position": range(1, len(results["rmsf_values"]) + 1),
                        "RMSF (Å)": results["rmsf_values"],
                    }
                )
                fig = px.line(
                    rmsf_data,
                    x="Residue Position",
                    y="RMSF (Å)",
                    title="RMSF per Residue",
                    template="plotly_dark",
                )
                # No need to include plotlyjs again if it is included in heatmap, BUT to be safe if heatmap is missing, include it?
                # If we include it twice, it's heavy but safe.
                # Optimization: Only include if heatmap didn't?
                # For robustness now, let's include it. It just increases file size.
                rmsf_div = pio.to_html(fig, full_html=False, include_plotlyjs=True)

            # 3. Ligand Table (Convert dict to HTML)
            ligand_html = ""
            if "ligand_analysis" in results:
                ligand_list = []
                for pdb, ligands in results["ligand_analysis"].items():
                    for lig in ligands:
                        ligand_list.append(
                            {
                                "Structure": pdb,
                                "Ligand": lig["name"],
                                "Residue ID": lig["id"],
                            }
                        )
                if ligand_list:
                    df = pd.DataFrame(ligand_list)
                    ligand_html = df.to_html(
                        classes="table table-dark table-striped", index=False
                    )

            # 4. Render Template
            template = Template(self.template_str)

            # Process insights for HTML (convert markdown bold to HTML bold)
            processed_insights = []
            if insights:
                for i in insights:
                    html_i = i.replace("**", "")  # Simple cleanup
                    processed_insights.append(html_i)

            html_content = template.render(
                date=datetime.now().strftime("%Y-%m-%d %H:%M"),
                stats=stats,
                insights=processed_insights,
                heatmap_div=heatmap_div,
                rmsf_div=rmsf_div,
                ligand_summary=ligand_html,
                pdb_content=pdb_content,
                dmol_js=dmol_js,
            )

            # Save File
            output_path = results["result_dir"] / "lab_notebook.html"
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            return output_path

        except Exception as e:
            import traceback

            logger.error(f"Error generating notebook: {str(e)}")
            logger.error(traceback.format_exc())
            return None
