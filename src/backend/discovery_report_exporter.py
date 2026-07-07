"""
Discovery Report Exporter Module.
Generates a standalone HTML report for a single Discover run - the
export/report-builder parity Compare mode has always had (PDF report,
HTML lab notebook), which Discover mode lacked. Unlike the Compare-mode
notebook, there's no 3D viewer or plot to embed here, so the report is a
plain, self-contained (no external CDN dependencies) HTML/CSS document -
more portable and shareable than the Bootstrap/3Dmol-based notebook.
"""

import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from jinja2 import Template

logger = logging.getLogger(__name__)

SOURCE_LABELS = {
    "pdb": "PDB",
    "alphafold": "AlphaFold",
    "swissmodel": "SWISS-MODEL",
    "esmfold": "ESMFold",
}


class DiscoveryReportExporter:
    """Generates a standalone HTML report from a DiscoveryCoordinator result."""

    def __init__(self):
        self.template_path = (
            Path(__file__).parent.parent
            / "resources"
            / "templates"
            / "discover_report_template.html"
        )
        self._template_str = None

    @property
    def template_str(self) -> str:
        if self._template_str is None:
            if self.template_path.exists():
                with open(self.template_path, "r", encoding="utf-8") as f:
                    self._template_str = f.read()
            else:
                self._template_str = (
                    "<html><body><h1>Discovery Report: {{ pdb_id }}</h1></body></html>"
                )
        return self._template_str

    def export(self, results: Dict[str, Any]) -> Path:
        """
        Renders `results` (the dict produced by
        DiscoveryCoordinator.run_discovery_pipeline, or the equivalent
        reloaded from history) into a standalone HTML report and writes it
        to a temp file.

        Returns:
            Path to the generated HTML file.
        """
        annotations = results.get("annotations")

        hit_rows = [
            {
                "target": str(h.get("target", ""))[:80],
                "prob": self._fmt(h.get("prob")),
                "eval": h.get("eval"),
                "seqId": h.get("seqId"),
            }
            for h in sorted(
                results.get("hits", []),
                key=lambda h: self._sort_key(h),
            )[:20]
        ]

        interaction_rows = []
        if annotations:
            for neighbor in annotations.get("per_neighbor", []):
                partners = neighbor.get("string_partners") or []
                pathways = neighbor.get("reactome_pathways") or []
                if not partners and not pathways:
                    continue
                interaction_rows.append(
                    {
                        "target": str(neighbor.get("target", ""))[:60],
                        "partners": ", ".join(
                            p.get("partner_name", "") for p in partners
                        )
                        or "-",
                        "pathways": ", ".join(p.get("name", "") for p in pathways)
                        or "-",
                    }
                )

        context = {
            "pdb_id": results.get("pdb_id", "?"),
            "source_label": SOURCE_LABELS.get(results.get("source"), "PDB"),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "hit_count": results.get("hit_count", 0),
            "databases_searched": ", ".join(results.get("databases_searched") or []),
            "annotations": annotations,
            "hit_rows": hit_rows,
            "interaction_rows": interaction_rows,
        }

        try:
            template = Template(self.template_str)
            html = template.render(**context)

            tmp_dir = Path(tempfile.mkdtemp(prefix="discover_report_"))
            output_path = (
                tmp_dir / f"discover_report_{results.get('pdb_id', 'run')}.html"
            )
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html)
            return output_path
        except Exception:
            logger.exception("Failed to generate discovery report")
            raise

    @staticmethod
    def _fmt(value: Any) -> Any:
        if isinstance(value, float):
            return f"{value:.3f}"
        return value

    @staticmethod
    def _sort_key(hit: Dict[str, Any]) -> float:
        try:
            return float(hit.get("eval", hit.get("eValue", hit.get("evalue", 1e9))))
        except (TypeError, ValueError):
            return 1e9
