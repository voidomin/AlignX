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

    @staticmethod
    def _prepare_stats(results):
        """Fills in display-friendly defaults for whichever stats fields a
        given pipeline run didn't populate, without mutating the caller's
        dict - the dashboard (results.py) expects `stats["mean_rmsd"]` to
        stay a float, not the formatted string this method produces."""
        stats = results.get("stats", {}).copy()
        if "mean_rmsd" in stats and isinstance(stats["mean_rmsd"], (int, float)):
            stats["mean_rmsd"] = f"{stats['mean_rmsd']:.3f}"
        elif "mean_rmsd" not in stats:
            stats["mean_rmsd"] = "N/A"

        stats.setdefault("num_structures", len(results.get("rmsd_df", [])))
        stats.setdefault("identity", stats.get("seq_identity", "N/A"))
        # Try to infer from alignment fasta or sequences if available
        stats.setdefault("chain_length", "N/A")
        return stats

    @staticmethod
    def _load_pdb_content(results):
        """PDB text for the embedded 3D viewer, with backticks escaped to
        avoid breaking the JS template literal it's embedded into."""
        alignment_pdb = results.get("alignment_pdb")
        if not alignment_pdb or not alignment_pdb.exists():
            return ""
        with open(alignment_pdb, "r") as f:
            return f.read().replace("`", "\\`")

    @staticmethod
    def _load_dmol_js():
        """Bundled 3Dmol.js, if present, so the notebook's 3D viewer works
        fully offline instead of depending on a CDN."""
        try:
            js_path = Path(__file__).parent / "resources" / "3Dmol-min.js"
            if js_path.exists():
                with open(js_path, "r", encoding="utf-8") as f:
                    return f.read()
        except Exception as e:
            logger.warning(f"Could not load local 3Dmol.js: {e}")
        return None

    @staticmethod
    def _heatmap_div(results):
        # Embed plotly.js to solve "empty" (CDN) issue by using include_plotlyjs=True
        heatmap_fig = results.get("heatmap_fig")
        if not heatmap_fig:
            return "<p>No Heatmap Available</p>"
        return pio.to_html(heatmap_fig, full_html=False, include_plotlyjs=True)

    @staticmethod
    def _rmsf_div(results):
        rmsf_values = results.get("rmsf_values")
        if not rmsf_values:
            return ""

        import plotly.express as px

        rmsf_data = pd.DataFrame(
            {
                "Residue Position": range(1, len(rmsf_values) + 1),
                "RMSF (Å)": rmsf_values,
            }
        )
        fig = px.line(
            rmsf_data,
            x="Residue Position",
            y="RMSF (Å)",
            title="RMSF per Residue",
            template="plotly_dark",
        )
        # Included even if the heatmap already embedded plotly.js - heavier,
        # but safe if the heatmap is ever missing.
        return pio.to_html(fig, full_html=False, include_plotlyjs=True)

    @staticmethod
    def _ligand_html(results):
        """Flattens {structure: [ligand, ...]} into one HTML table, or ""
        if this run has no ligand analysis / no ligands were found."""
        if "ligand_analysis" not in results:
            return ""

        ligand_list = [
            {"Structure": pdb, "Ligand": lig["name"], "Residue ID": lig["id"]}
            for pdb, ligands in results["ligand_analysis"].items()
            for lig in ligands
        ]
        if not ligand_list:
            return ""

        df = pd.DataFrame(ligand_list)
        return df.to_html(classes="table table-dark table-striped", index=False)

    @staticmethod
    def _processed_insights(insights):
        # Convert markdown bold to HTML bold (simple cleanup)
        return [i.replace("**", "") for i in insights] if insights else []

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
            template = Template(self.template_str)
            html_content = template.render(
                date=datetime.now().strftime("%Y-%m-%d %H:%M"),
                stats=self._prepare_stats(results),
                insights=self._processed_insights(insights),
                heatmap_div=self._heatmap_div(results),
                rmsf_div=self._rmsf_div(results),
                ligand_summary=self._ligand_html(results),
                pdb_content=self._load_pdb_content(results),
                dmol_js=self._load_dmol_js(),
            )

            output_path = results["result_dir"] / "lab_notebook.html"
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            return output_path

        except Exception:
            logger.exception("Error generating notebook")
            return None
