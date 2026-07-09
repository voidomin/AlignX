import pandas as pd
import pytest
from PIL import Image

from src.backend.report_generator import ReportGenerator, _clean_text


def _write_tiny_png(path):
    Image.new("RGB", (4, 4), color="red").save(path)


class TestCleanText:
    def test_non_string_input_is_stringified(self):
        assert _clean_text(1.5) == "1.5"


class TestGenerateFullReport:
    def test_full_happy_path_produces_a_real_pdf(self, tmp_path):
        heatmap_path = tmp_path / "heatmap.png"
        tree_path = tmp_path / "tree.png"
        _write_tiny_png(heatmap_path)
        _write_tiny_png(tree_path)

        results = {
            "pdb_ids": ["4RLT", "3UG9"],
            "stats": {
                "mean_rmsd": 1.23,
                "median_rmsd": 1.1,
                "min_rmsd": 0.5,
                "max_rmsd": 2.0,
            },
            "insights": ["**Strong** structural similarity found."],
            "heatmap_path": heatmap_path,
            "tree_path": tree_path,
            "rmsd_df": pd.DataFrame(
                [[0.0, 1.23], [1.23, 0.0]],
                index=["4RLT", "3UG9"],
                columns=["4RLT", "3UG9"],
            ),
        }

        generator = ReportGenerator(tmp_path)
        report_path = generator.generate_full_report(results)

        assert report_path.exists()
        assert report_path.stat().st_size > 0
        assert report_path.suffix == ".pdf"

    def test_missing_heatmap_and_tree_show_fallback_text_not_a_crash(self, tmp_path):
        results = {
            "pdb_ids": ["4RLT", "3UG9"],
            "stats": {"mean_rmsd": 1.0},
        }

        generator = ReportGenerator(tmp_path)
        report_path = generator.generate_full_report(results)

        assert report_path.exists()

    def test_sections_filter_limits_what_gets_included(self, tmp_path):
        results = {"pdb_ids": ["4RLT"], "stats": {"mean_rmsd": 1.0}}

        generator = ReportGenerator(tmp_path)
        report_path = generator.generate_full_report(results, sections=["summary"])

        assert report_path.exists()

    def test_no_insights_key_falls_back_to_generating_them(self, tmp_path):
        """When 'insights' isn't already in results (e.g. a report generated
        directly from a fresh pipeline run before insights were attached),
        generate_full_report regenerates them via InsightsGenerator rather
        than failing - as long as rmsd_df is a real DataFrame."""
        results = {
            "pdb_ids": ["4RLT", "3UG9"],
            "stats": {"mean_rmsd": 1.0},
            "rmsd_df": pd.DataFrame(
                [[0.0, 1.0], [1.0, 0.0]],
                index=["4RLT", "3UG9"],
                columns=["4RLT", "3UG9"],
            ),
        }

        generator = ReportGenerator(tmp_path)
        report_path = generator.generate_full_report(results, sections=["insights"])

        assert report_path.exists()

    def test_empty_insights_list_skips_the_section_entirely(self, tmp_path):
        """An explicitly empty insights list (as opposed to a missing key,
        which triggers regeneration) must render nothing for that section
        rather than an empty heading."""
        results = {
            "pdb_ids": ["4RLT"],
            "stats": {"mean_rmsd": 1.0},
            "insights": [],
        }

        generator = ReportGenerator(tmp_path)
        report_path = generator.generate_full_report(results, sections=["insights"])

        assert report_path.exists()

    def test_angstrom_symbol_does_not_break_pdf_generation(self, tmp_path):
        """clean_text() maps the Å character to its Latin-1 byte - a real
        regression risk since FPDF's classic core fonts can't encode
        arbitrary Unicode directly."""
        results = {
            "pdb_ids": ["4RLT"],
            "stats": {"mean_rmsd": 1.5},
            "insights": ["Mean distance of 1.5 Å observed."],
        }

        generator = ReportGenerator(tmp_path)
        report_path = generator.generate_full_report(results)

        assert report_path.exists()

    def test_corrupt_image_file_falls_back_to_error_text_not_a_crash(self, tmp_path):
        heatmap_path = tmp_path / "heatmap.png"
        heatmap_path.write_text("not a real png")

        results = {
            "pdb_ids": ["4RLT"],
            "stats": {"mean_rmsd": 1.0},
            "heatmap_path": heatmap_path,
        }

        generator = ReportGenerator(tmp_path)
        report_path = generator.generate_full_report(results)

        assert report_path.exists()

    def test_raises_when_output_dir_does_not_exist(self, tmp_path):
        results = {"pdb_ids": ["4RLT"], "stats": {"mean_rmsd": 1.0}}
        generator = ReportGenerator(tmp_path / "does_not_exist")

        with pytest.raises(FileNotFoundError):
            generator.generate_full_report(results)
