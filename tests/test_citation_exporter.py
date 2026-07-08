import pytest

from src.backend.citation_exporter import (
    CitationExporter,
    citations_for_compare_run,
    citations_for_discover_run,
    _structure_source_citation,
)


class TestStructureSourceCitation:
    def test_pdb_id_cites_pdb(self):
        assert _structure_source_citation("4RLT") == "pdb"

    def test_alphafold_id_cites_alphafold_db(self):
        assert _structure_source_citation("AF-P69905-F1") == "alphafold_db"

    def test_swissmodel_id_cites_swissmodel(self):
        assert _structure_source_citation("SM-P69905") == "swissmodel"

    def test_esmfold_id_cites_esm_atlas(self):
        assert _structure_source_citation("ESM-MGYP002537940442") == "esm_atlas"


class TestCitationsForCompareRun:
    def test_always_includes_mustang(self):
        assert "mustang" in citations_for_compare_run(["4RLT"])

    def test_includes_one_entry_per_distinct_source(self):
        ids = citations_for_compare_run(["4RLT", "AF-P69905-F1", "3UG9"])
        assert ids == ["mustang", "pdb", "alphafold_db"]

    def test_does_not_duplicate_the_same_source(self):
        ids = citations_for_compare_run(["4RLT", "3UG9", "1CRN"])
        assert ids.count("pdb") == 1

    def test_empty_pdb_ids_still_cites_mustang(self):
        assert citations_for_compare_run([]) == ["mustang"]

    def test_none_pdb_ids_does_not_raise(self):
        assert citations_for_compare_run(None) == ["mustang"]


class TestCitationsForDiscoverRun:
    def test_always_includes_foldseek_and_query_source(self):
        ids = citations_for_discover_run({"pdb_id": "4RLT", "databases_searched": []})
        assert "foldseek" in ids
        assert "pdb" in ids

    def test_cites_afdb_when_afdb_database_searched(self):
        ids = citations_for_discover_run(
            {"pdb_id": "4RLT", "databases_searched": ["afdb50"]}
        )
        assert "alphafold_db" in ids

    def test_cites_sifts_when_pdb100_searched(self):
        ids = citations_for_discover_run(
            {"pdb_id": "4RLT", "databases_searched": ["pdb100"]}
        )
        assert "sifts" in ids

    def test_does_not_cite_sifts_when_no_sifts_trigger_db_searched(self):
        ids = citations_for_discover_run(
            {"pdb_id": "4RLT", "databases_searched": ["afdb50"]}
        )
        assert "sifts" not in ids

    def test_cites_only_annotation_sources_that_actually_contributed_data(self):
        results = {
            "pdb_id": "4RLT",
            "databases_searched": [],
            "annotations": {
                "per_neighbor": [
                    {"domains": ["PF00001"], "go_terms": []},
                    {"domains": [], "go_terms": ["GO:0001"]},
                ]
            },
        }
        ids = citations_for_discover_run(results)
        assert "interpro" in ids
        assert "quickgo" in ids
        assert "string" not in ids
        assert "reactome" not in ids

    def test_no_annotation_data_cites_no_annotation_sources(self):
        ids = citations_for_discover_run(
            {"pdb_id": "4RLT", "databases_searched": [], "annotations": {}}
        )
        assert "interpro" not in ids
        assert "quickgo" not in ids


class TestCitationExporterExport:
    def test_valid_run_id_produces_a_real_file_with_both_sections(self, tmp_path):
        exporter = CitationExporter()
        path = exporter.export(["mustang", "pdb"], "run_1234567890_abc123", "3.26.0")

        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "run_1234567890_abc123" in content
        assert "== Plain text ==" in content
        assert "== BibTeX ==" in content
        assert "MUSTANG" in content
        assert "3.26.0" in content
        path.unlink()

    def test_structscope_is_always_included_even_if_not_requested(self, tmp_path):
        exporter = CitationExporter()
        path = exporter.export([], "run_abc", "1.0.0")

        content = path.read_text(encoding="utf-8")
        assert "StructScope v1.0.0" in content
        path.unlink()

    def test_rejects_run_id_with_path_traversal(self):
        exporter = CitationExporter()
        with pytest.raises(ValueError):
            exporter.export(["mustang"], "../../etc/passwd")

    def test_rejects_run_id_with_path_separator(self):
        exporter = CitationExporter()
        with pytest.raises(ValueError):
            exporter.export(["mustang"], "some/path")

    def test_rejects_empty_run_id(self):
        exporter = CitationExporter()
        with pytest.raises(ValueError):
            exporter.export(["mustang"], "")
