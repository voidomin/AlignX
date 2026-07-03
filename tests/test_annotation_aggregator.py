from unittest.mock import patch, AsyncMock, MagicMock

import httpx
import pytest

from src.backend.annotation_aggregator import AnnotationAggregator


class TestExtractUniprotAccession:

    def test_extracts_from_afdb_target(self):
        target = "AF-P01541-F1-model_v6 Denclatoxin-B"
        assert AnnotationAggregator.extract_uniprot_accession(target) == "P01541"

    def test_extracts_case_insensitively(self):
        target = "af-q43226-f1-model_v6 Thionin class 1"
        assert AnnotationAggregator.extract_uniprot_accession(target) == "Q43226"

    def test_returns_none_for_pdb_target(self):
        target = "1ab1-assembly1.cif.gz_A SI FORM CRAMBIN"
        assert AnnotationAggregator.extract_uniprot_accession(target) is None

    def test_returns_none_for_empty_target(self):
        assert AnnotationAggregator.extract_uniprot_accession("") is None


def _mock_response(status_code=200, json_data=None):
    response = AsyncMock()
    response.status_code = status_code
    response.json = MagicMock(return_value=json_data or {})
    return response


class TestFetchInterproEntries:

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_parses_entries_and_embedded_go_terms(self, mock_get):
        mock_get.return_value = _mock_response(
            json_data={
                "results": [
                    {
                        "metadata": {
                            "accession": "IPR001010",
                            "name": "Thionin",
                            "type": "family",
                            "go_terms": [
                                {
                                    "identifier": "GO:0006952",
                                    "name": "defense response",
                                    "category": {"name": "biological_process"},
                                }
                            ],
                        }
                    }
                ]
            }
        )
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            entries = await aggregator.fetch_interpro_entries("P01541", client)

        assert len(entries) == 1
        assert entries[0]["name"] == "Thionin"
        assert entries[0]["go_terms"] == [
            {"id": "GO:0006952", "name": "defense response", "aspect": "biological_process"}
        ]

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_returns_empty_on_non_200(self, mock_get):
        mock_get.return_value = _mock_response(status_code=404)
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            entries = await aggregator.fetch_interpro_entries("NOPE", client)
        assert entries == []


class TestFetchQuickgoAnnotations:

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_parses_annotations(self, mock_get):
        mock_get.return_value = _mock_response(
            json_data={
                "results": [
                    {
                        "goId": "GO:0090729",
                        "goAspect": "molecular_function",
                        "qualifier": "enables",
                        "goEvidence": "IEA",
                    }
                ]
            }
        )
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            terms = await aggregator.fetch_quickgo_annotations("P01541", client)

        assert terms == [
            {
                "id": "GO:0090729",
                "aspect": "molecular_function",
                "qualifier": "enables",
                "evidence": "IEA",
            }
        ]


class TestResolveGoTermNames:

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_resolves_names_for_ids(self, mock_get):
        mock_get.return_value = _mock_response(
            json_data={"results": [{"id": "GO:0090729", "name": "toxin activity"}]}
        )
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            names = await aggregator.resolve_go_term_names(["GO:0090729"], client)
        assert names == {"GO:0090729": "toxin activity"}

    @pytest.mark.asyncio
    async def test_empty_input_makes_no_request(self):
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            names = await aggregator.resolve_go_term_names([], client)
        assert names == {}


class TestAggregateForHits:

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.resolve_go_term_names")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_quickgo_annotations")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_interpro_entries")
    async def test_aggregates_domains_and_go_terms_across_neighbors(
        self, mock_interpro, mock_quickgo, mock_resolve
    ):
        def interpro_side_effect(accession, client):
            if accession == "P01541":
                return [
                    {
                        "accession": "IPR001010",
                        "name": "Thionin",
                        "type": "family",
                        "go_terms": [
                            {
                                "id": "GO:0006952",
                                "name": "defense response",
                                "aspect": "biological_process",
                            }
                        ],
                    }
                ]
            if accession == "Q43226":
                return [
                    {
                        "accession": "IPR001010",
                        "name": "Thionin",
                        "type": "family",
                        "go_terms": [],
                    }
                ]
            return []

        async def quickgo_side_effect(accession, client):
            return []

        mock_interpro.side_effect = interpro_side_effect
        mock_quickgo.side_effect = quickgo_side_effect
        mock_resolve.return_value = {}

        hits = [
            {"target": "AF-P01541-F1-model_v6 Denclatoxin-B", "eval": 2.168e-05},
            {"target": "AF-Q43226-F1-model_v6 Thionin class 1", "eval": 0.00164},
            # Unresolvable (no UniProt accession embedded) - must be excluded
            # from ranking entirely, not just left unannotated, so it can't
            # crowd out a resolvable hit further down the real hit list.
            {"target": "1ab1-assembly1.cif.gz_A SI FORM CRAMBIN", "eval": 0.0000001},
        ]

        aggregator = AnnotationAggregator()
        result = await aggregator.aggregate_for_hits(hits, top_n_neighbors=10)

        assert result["neighbors_considered"] == 2
        assert result["total_hit_count"] == 3
        assert result["resolvable_hit_count"] == 2
        assert result["annotated_neighbor_count"] == 2
        assert result["unannotated_neighbor_count"] == 0
        assert result["top_domains"][0]["name"] == "Thionin"
        assert result["top_domains"][0]["neighbor_count"] == 2
        assert result["top_go_terms"][0]["id"] == "GO:0006952"
        assert result["top_go_terms"][0]["neighbor_count"] == 1

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.resolve_go_term_names")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_quickgo_annotations")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_interpro_entries")
    async def test_unresolvable_hits_cannot_crowd_out_resolvable_ones(
        self, mock_interpro, mock_quickgo, mock_resolve
    ):
        """Regression test for a real gap found live-testing 1CRN: a wall of
        near-identical PDB100 hits (re-solved structures of the exact same
        protein) can have far lower E-values than every AFDB hit, so ranking
        top_n across ALL hits before filtering left zero annotatable
        neighbors even though good AFDB matches existed. Filtering to
        resolvable hits first fixes this."""
        mock_interpro.return_value = [{"accession": "IPR001010", "name": "Thionin", "type": "family", "go_terms": []}]
        mock_quickgo.return_value = []
        mock_resolve.return_value = {}

        # 15 unresolvable PDB hits, all with far smaller E-values than the
        # one resolvable AFDB hit.
        pdb_hits = [
            {"target": f"{i}xyz-assembly1.cif.gz_A SAME PROTEIN", "eval": 1e-12}
            for i in range(15)
        ]
        afdb_hit = {"target": "AF-P01541-F1-model_v6 Denclatoxin-B", "eval": 2.168e-05}
        hits = pdb_hits + [afdb_hit]

        aggregator = AnnotationAggregator()
        result = await aggregator.aggregate_for_hits(hits, top_n_neighbors=10)

        assert result["total_hit_count"] == 16
        assert result["resolvable_hit_count"] == 1
        assert result["neighbors_considered"] == 1
        assert result["annotated_neighbor_count"] == 1
        assert result["top_domains"][0]["name"] == "Thionin"

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.resolve_go_term_names")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_quickgo_annotations")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_interpro_entries")
    async def test_respects_top_n_neighbors_limit(
        self, mock_interpro, mock_quickgo, mock_resolve
    ):
        mock_interpro.return_value = []
        mock_quickgo.return_value = []
        mock_resolve.return_value = {}

        hits = [
            {"target": f"AF-P0000{i}-F1-model_v6 X", "eval": i * 0.001} for i in range(5)
        ]

        aggregator = AnnotationAggregator()
        result = await aggregator.aggregate_for_hits(hits, top_n_neighbors=2)

        assert result["neighbors_considered"] == 2
        assert mock_interpro.call_count == 2
