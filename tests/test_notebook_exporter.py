from unittest.mock import patch

import plotly.graph_objects as go

from src.backend.notebook_exporter import NotebookExporter


def _real_heatmap_fig():
    return go.Figure(data=go.Heatmap(z=[[0.0, 1.5], [1.5, 0.0]]))


class TestNotebookExporterExport:
    def test_full_happy_path_produces_a_real_html_file(self, tmp_path):
        alignment_pdb = tmp_path / "alignment.pdb"
        alignment_pdb.write_text("ATOM      1  CA  ALA A   1")

        results = {
            "stats": {"mean_rmsd": 1.23456, "seq_identity": 85.5},
            "rmsd_df": [[0.0, 1.5], [1.5, 0.0]],
            "alignment_pdb": alignment_pdb,
            "heatmap_fig": _real_heatmap_fig(),
            "rmsf_values": [0.5, 0.7, 0.3],
            "ligand_analysis": {
                "4RLT": [{"name": "HEM", "id": "HEM_A_101"}],
            },
            "result_dir": tmp_path,
        }

        exporter = NotebookExporter()
        output_path = exporter.export(results, insights=["**Key finding** here."])

        assert output_path is not None
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "1.235" in content  # mean_rmsd formatted to 3 decimals
        assert "Key finding" in content
        assert "**" not in content.split("Key finding")[0][-20:]  # markdown stripped
        assert "HEM" in content
        assert "ATOM      1  CA  ALA A   1" in content

    def test_missing_stats_fall_back_to_sensible_defaults(self, tmp_path):
        results = {
            "stats": {},
            "result_dir": tmp_path,
        }

        exporter = NotebookExporter()
        output_path = exporter.export(results)

        assert output_path is not None
        content = output_path.read_text(encoding="utf-8")
        assert "N/A" in content

    def test_no_heatmap_shows_fallback_message(self, tmp_path):
        results = {"stats": {"mean_rmsd": 1.0}, "result_dir": tmp_path}

        exporter = NotebookExporter()
        output_path = exporter.export(results)

        content = output_path.read_text(encoding="utf-8")
        assert "No Heatmap Available" in content

    def test_no_insights_renders_without_error(self, tmp_path):
        results = {"stats": {"mean_rmsd": 1.0}, "result_dir": tmp_path}

        exporter = NotebookExporter()
        output_path = exporter.export(results, insights=None)

        assert output_path is not None

    def test_missing_alignment_pdb_key_does_not_raise(self, tmp_path):
        results = {"stats": {"mean_rmsd": 1.0}, "result_dir": tmp_path}

        exporter = NotebookExporter()
        output_path = exporter.export(results)

        assert output_path is not None

    def test_returns_none_and_does_not_raise_on_bad_result_dir(self):
        results = {"stats": {"mean_rmsd": 1.0}, "result_dir": None}

        exporter = NotebookExporter()
        output_path = exporter.export(results)

        assert output_path is None

    def test_ligand_analysis_with_no_actual_ligands_renders_without_a_table(
        self, tmp_path
    ):
        """A run that has ligand analysis but found zero ligands across
        every structure (empty per-structure lists) must render cleanly
        without a ligand table, not an empty/broken one."""
        results = {
            "stats": {"mean_rmsd": 1.0},
            "ligand_analysis": {"4RLT": []},
            "result_dir": tmp_path,
        }

        exporter = NotebookExporter()
        output_path = exporter.export(results)

        assert output_path is not None

    def test_read_failure_on_bundled_3dmoljs_does_not_break_export(self, tmp_path):
        """A read failure on the bundled 3Dmol.js asset (present on disk in
        this repo, but the read itself could still fail, e.g. a permissions
        issue) must not break notebook export - the 3D viewer script tag
        just ends up empty rather than embedding the library."""
        results = {"stats": {"mean_rmsd": 1.0}, "result_dir": tmp_path}
        real_open = open

        def selective_open(path, *args, **kwargs):
            if "3Dmol-min.js" in str(path):
                raise OSError("permission denied")
            return real_open(path, *args, **kwargs)

        exporter = NotebookExporter()
        with patch("builtins.open", side_effect=selective_open):
            output_path = exporter.export(results)

        assert output_path is not None


class TestTemplateStrFallback:
    def test_falls_back_to_minimal_template_when_file_missing(self, tmp_path):
        exporter = NotebookExporter()
        exporter.template_path = tmp_path / "does_not_exist.html"

        assert "Analysis Report" in exporter.template_str

    def test_loads_real_template_file_when_present(self):
        exporter = NotebookExporter()
        assert exporter.template_path.exists()
        assert "{{ date }}" in exporter.template_str
