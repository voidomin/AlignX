from src.backend.discovery_report_exporter import DiscoveryReportExporter


def _make_results(**overrides):
    results = {
        "pdb_id": "1CRN",
        "source": "pdb",
        "databases_searched": ["pdb100", "afdb50"],
        "hit_count": 2,
        "hits": [
            {
                "target": "AF-P01541-F1-model_v6 Denclatoxin-B",
                "prob": 1.0,
                "eval": 2.168e-05,
                "seqId": 50,
            },
            {
                "target": "AF-Q43226-F1-model_v6 Thionin class 1",
                "prob": 1.0,
                "eval": 0.00164,
                "seqId": 46.6,
            },
        ],
        "annotations": {
            "neighbors_considered": 2,
            "total_hit_count": 2,
            "candidates_examined": 2,
            "resolvable_hit_count": 2,
            "annotated_neighbor_count": 2,
            "unannotated_neighbor_count": 0,
            "neighbors_with_interactions_count": 1,
            "neighbors_with_pathways_count": 0,
            "top_domains": [
                {"name": "Thionin", "type": "family", "neighbor_count": 2},
            ],
            "top_go_terms": [
                {
                    "id": "GO:0006952",
                    "name": "defense response",
                    "aspect": "biological_process",
                    "neighbor_count": 2,
                },
            ],
            "per_neighbor": [
                {
                    "target": "AF-P01541-F1-model_v6 Denclatoxin-B",
                    "accession": "P01541",
                    "string_partners": [{"partner_name": "MDM2", "score": 0.9}],
                    "reactome_pathways": [],
                },
                {
                    "target": "AF-Q43226-F1-model_v6 Thionin class 1",
                    "accession": "Q43226",
                    "string_partners": [],
                    "reactome_pathways": [],
                },
            ],
        },
    }
    results.update(overrides)
    return results


def test_export_writes_an_html_file():
    exporter = DiscoveryReportExporter()
    path = exporter.export(_make_results())

    assert path.exists()
    assert path.suffix == ".html"
    html = path.read_text(encoding="utf-8")
    assert "1CRN" in html


def test_export_includes_domain_and_go_term_tables():
    exporter = DiscoveryReportExporter()
    path = exporter.export(_make_results())
    html = path.read_text(encoding="utf-8")

    assert "Thionin" in html
    assert "defense response" in html


def test_export_includes_interaction_rows_for_neighbors_with_data():
    exporter = DiscoveryReportExporter()
    path = exporter.export(_make_results())
    html = path.read_text(encoding="utf-8")

    assert "MDM2" in html


def test_export_shows_empty_state_when_no_annotations(tmp_path):
    exporter = DiscoveryReportExporter()
    path = exporter.export(_make_results(annotations=None))
    html = path.read_text(encoding="utf-8")

    assert "No annotation data available" in html


def test_export_shows_empty_state_when_no_domains_or_go_terms():
    results = _make_results()
    results["annotations"]["top_domains"] = []
    results["annotations"]["top_go_terms"] = []
    results["annotations"]["per_neighbor"] = []

    exporter = DiscoveryReportExporter()
    path = exporter.export(results)
    html = path.read_text(encoding="utf-8")

    assert "No common domain/family found" in html
    assert "No common GO term found" in html
    assert "No STRING interaction or Reactome pathway data found" in html


def test_export_handles_missing_hits_gracefully():
    results = _make_results(hits=[], hit_count=0)
    exporter = DiscoveryReportExporter()
    path = exporter.export(results)
    html = path.read_text(encoding="utf-8")

    assert "No structural matches found" in html


def test_export_sorts_hits_by_evalue_and_caps_at_20():
    hits = [
        {"target": f"hit_{i}", "prob": 0.5, "eval": float(i), "seqId": 10}
        for i in range(25)
    ]
    results = _make_results(hits=hits, hit_count=25)

    exporter = DiscoveryReportExporter()
    path = exporter.export(results)
    html = path.read_text(encoding="utf-8")

    assert "hit_0" in html  # lowest eval, most confident, must be included
    assert "hit_24" not in html  # beyond the top-20 cap
