from unittest.mock import patch, AsyncMock, MagicMock

import httpx
import pytest

from src.backend.annotation_aggregator import AnnotationAggregator


@pytest.fixture(autouse=True)
def fast_string_rate_limiter():
    """_string_rate_limiter is a class-level singleton (shared across all
    AnnotationAggregator instances, like FoldseekClient's rate limiter) -
    zero it out for the duration of these tests and restore it after, so
    one test setting it to 0 can't silently disable rate limiting for
    every test that runs after it in the same process."""
    original = AnnotationAggregator._string_rate_limiter._min_interval
    AnnotationAggregator._string_rate_limiter._min_interval = 0
    AnnotationAggregator._string_rate_limiter._last_request_at = 0.0
    yield
    AnnotationAggregator._string_rate_limiter._min_interval = original


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


class TestExtractPdbChain:

    def test_extracts_pdb_id_and_chain(self):
        target = "1ab1-assembly1.cif.gz_A SI FORM CRAMBIN"
        assert AnnotationAggregator.extract_pdb_chain(target) == ("1AB1", "A")

    def test_strips_assembly_copy_suffix_from_chain(self):
        target = "2ij9-assembly1.cif.gz_A-2 Crystal Structure of Uridylate Kinase"
        assert AnnotationAggregator.extract_pdb_chain(target) == ("2IJ9", "A")

    def test_returns_none_for_afdb_target(self):
        target = "AF-P01541-F1-model_v6 Denclatoxin-B"
        assert AnnotationAggregator.extract_pdb_chain(target) is None

    def test_returns_none_for_empty_target(self):
        assert AnnotationAggregator.extract_pdb_chain("") is None


def _mock_response(status_code=200, json_data=None):
    response = AsyncMock()
    response.status_code = status_code
    response.json = MagicMock(return_value=json_data or {})
    return response


class TestGetOrFetch:
    """Tests for the persistent-cache wrapper every fetch_* method routes
    through. A mocked cache_db (duck-typed: get_annotation_cache /
    set_annotation_cache) stands in for HistoryDatabase here - the real
    integration with HistoryDatabase is covered by tests/test_database.py."""

    @pytest.mark.asyncio
    async def test_cache_hit_skips_fetch_fn(self):
        cache_db = MagicMock()
        cache_db.get_annotation_cache.return_value = '{"cached": true}'
        aggregator = AnnotationAggregator(cache_db=cache_db)
        fetch_fn = AsyncMock()

        result = await aggregator._get_or_fetch("key1", "svc", fetch_fn)

        assert result == {"cached": True}
        fetch_fn.assert_not_called()

    @pytest.mark.asyncio
    async def test_cache_miss_calls_fetch_fn_and_stores_result(self):
        cache_db = MagicMock()
        cache_db.get_annotation_cache.return_value = None
        aggregator = AnnotationAggregator(cache_db=cache_db)
        fetch_fn = AsyncMock(return_value=[{"name": "Thionin"}])

        result = await aggregator._get_or_fetch("key1", "svc", fetch_fn)

        assert result == [{"name": "Thionin"}]
        fetch_fn.assert_called_once()
        cache_db.set_annotation_cache.assert_called_once_with(
            "key1", "svc", '[{"name": "Thionin"}]'
        )

    @pytest.mark.asyncio
    async def test_no_cache_db_always_calls_fetch_fn(self):
        aggregator = AnnotationAggregator(cache_db=None)
        fetch_fn = AsyncMock(return_value=["fresh"])

        result = await aggregator._get_or_fetch("key1", "svc", fetch_fn)

        assert result == ["fresh"]
        fetch_fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_read_failure_falls_back_to_fetch_fn(self):
        """A broken cache must degrade to "as if there were no cache", not
        break the whole annotation step."""
        cache_db = MagicMock()
        cache_db.get_annotation_cache.side_effect = RuntimeError("db is locked")
        aggregator = AnnotationAggregator(cache_db=cache_db)
        fetch_fn = AsyncMock(return_value=["fresh"])

        result = await aggregator._get_or_fetch("key1", "svc", fetch_fn)

        assert result == ["fresh"]
        fetch_fn.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_write_failure_does_not_lose_the_result(self):
        cache_db = MagicMock()
        cache_db.get_annotation_cache.return_value = None
        cache_db.set_annotation_cache.side_effect = RuntimeError("disk full")
        aggregator = AnnotationAggregator(cache_db=cache_db)
        fetch_fn = AsyncMock(return_value=["fresh"])

        result = await aggregator._get_or_fetch("key1", "svc", fetch_fn)

        assert result == ["fresh"]


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

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_second_call_for_same_accession_uses_cache_not_network(self, mock_get):
        """End-to-end proof that a real fetch method (not just the isolated
        _get_or_fetch wrapper) actually skips the network on a cache hit."""
        mock_get.return_value = _mock_response(
            json_data={"results": [{"metadata": {"name": "Thionin", "type": "family"}}]}
        )
        cache_db = MagicMock()
        stored = {}
        cache_db.get_annotation_cache.side_effect = lambda key, *a, **k: stored.get(key)
        cache_db.set_annotation_cache.side_effect = (
            lambda key, service, payload: stored.update({key: payload})
        )
        aggregator = AnnotationAggregator(cache_db=cache_db)

        async with httpx.AsyncClient() as client:
            first = await aggregator.fetch_interpro_entries("P01541", client)
            second = await aggregator.fetch_interpro_entries("P01541", client)

        assert first == second
        assert mock_get.call_count == 1  # second call served entirely from cache


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


class TestFetchStringPartners:

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_taxon_id(self):
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            partners = await aggregator.fetch_string_partners("P04637", None, client)
        assert partners == []

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.post")
    async def test_parses_partners(self, mock_post):
        aggregator = AnnotationAggregator()
        mock_post.return_value = _mock_response(
            json_data=[
                {"preferredName_A": "TP53", "preferredName_B": "SFN", "score": 0.999},
                {"preferredName_A": "TP53", "preferredName_B": "EP300", "score": 0.999},
            ]
        )
        async with httpx.AsyncClient() as client:
            partners = await aggregator.fetch_string_partners("P04637", 9606, client)

        assert partners == [
            {"partner_name": "SFN", "score": 0.999},
            {"partner_name": "EP300", "score": 0.999},
        ]

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.post")
    async def test_returns_empty_for_unknown_organism(self, mock_post):
        """STRING only covers organisms with a sequenced genome - most
        Foldseek AFDB hits won't be covered at all, and that must degrade
        gracefully rather than error."""
        aggregator = AnnotationAggregator()
        mock_post.return_value = _mock_response(
            json_data=[{"Error": "unknown organism", "ErrorMessage": "..."}]
        )
        async with httpx.AsyncClient() as client:
            partners = await aggregator.fetch_string_partners("P01541", 3965, client)
        assert partners == []


class TestFetchReactomePathways:

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_parses_pathways(self, mock_get):
        mock_get.return_value = _mock_response(
            json_data=[
                {"stId": "R-HSA-111448", "displayName": "Activation of NOXA"},
                {"stId": "R-HSA-139915", "displayName": "Activation of PUMA"},
            ]
        )
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            pathways = await aggregator.fetch_reactome_pathways("P04637", client)

        assert pathways == [
            {"id": "R-HSA-111448", "name": "Activation of NOXA"},
            {"id": "R-HSA-139915", "name": "Activation of PUMA"},
        ]

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_returns_empty_on_non_200(self, mock_get):
        mock_get.return_value = _mock_response(status_code=404)
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            pathways = await aggregator.fetch_reactome_pathways("NOPE", client)
        assert pathways == []


class TestResolvePdbUniprotAccession:

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_resolves_chain_to_accession(self, mock_get):
        mock_get.return_value = _mock_response(
            json_data={
                "1crn": {
                    "UniProt": {
                        "P01542": {
                            "name": "CRAM_CRAAB",
                            "mappings": [{"chain_id": "A", "identity": 0.98}],
                        }
                    }
                }
            }
        )
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            accession = await aggregator.resolve_pdb_uniprot_accession("1CRN", "A", client)
        assert accession == "P01542"

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_returns_none_for_unmapped_chain(self, mock_get):
        mock_get.return_value = _mock_response(
            json_data={
                "1abc": {
                    "UniProt": {
                        "P00000": {"mappings": [{"chain_id": "B"}]},
                    }
                }
            }
        )
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            accession = await aggregator.resolve_pdb_uniprot_accession("1ABC", "A", client)
        assert accession is None

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_returns_none_on_non_200(self, mock_get):
        mock_get.return_value = _mock_response(status_code=404)
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            accession = await aggregator.resolve_pdb_uniprot_accession("ZZZZ", "A", client)
        assert accession is None

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_uses_cache_to_avoid_refetching_same_entry(self, mock_get):
        """Multiple hits/chains from the same PDB entry (common - a
        well-studied protein is often deposited many times) shouldn't
        trigger a fresh SIFTS call each time."""
        mock_get.return_value = _mock_response(
            json_data={
                "1crn": {
                    "UniProt": {
                        "P01542": {"mappings": [{"chain_id": "A"}]},
                    }
                }
            }
        )
        aggregator = AnnotationAggregator()
        cache = {}
        async with httpx.AsyncClient() as client:
            first = await aggregator.resolve_pdb_uniprot_accession("1CRN", "A", client, cache)
            second = await aggregator.resolve_pdb_uniprot_accession("1CRN", "A", client, cache)

        assert first == "P01542"
        assert second == "P01542"
        mock_get.assert_called_once()


class TestResolveAccession:

    @pytest.mark.asyncio
    async def test_prefers_afdb_regex_over_sifts_lookup(self):
        aggregator = AnnotationAggregator()
        with patch.object(
            aggregator, "resolve_pdb_uniprot_accession", new_callable=AsyncMock
        ) as mock_sifts:
            hit = {"target": "AF-P01541-F1-model_v6 Denclatoxin-B"}
            async with httpx.AsyncClient() as client:
                accession = await aggregator.resolve_accession(hit, client)
            assert accession == "P01541"
            mock_sifts.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_sifts_for_pdb_targets(self):
        aggregator = AnnotationAggregator()
        with patch.object(
            aggregator, "resolve_pdb_uniprot_accession", new_callable=AsyncMock
        ) as mock_sifts:
            mock_sifts.return_value = "P01542"
            hit = {"target": "1ab1-assembly1.cif.gz_A SI FORM CRAMBIN"}
            async with httpx.AsyncClient() as client:
                accession = await aggregator.resolve_accession(hit, client)
            assert accession == "P01542"
            mock_sifts.assert_called_once_with("1AB1", "A", client, None)

    @pytest.mark.asyncio
    async def test_returns_none_for_unresolvable_target(self):
        aggregator = AnnotationAggregator()
        hit = {"target": "gmgcl-some-unrelated-format"}
        async with httpx.AsyncClient() as client:
            accession = await aggregator.resolve_accession(hit, client)
        assert accession is None


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
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.resolve_pdb_uniprot_accession")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_reactome_pathways")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_string_partners")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_quickgo_annotations")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_interpro_entries")
    async def test_aggregates_domains_and_go_terms_across_neighbors(
        self, mock_interpro, mock_quickgo, mock_string, mock_reactome, mock_pdb_sifts, mock_resolve
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
        mock_string.return_value = []
        mock_reactome.return_value = []
        mock_pdb_sifts.return_value = None  # simulate: no SIFTS mapping for this entry
        mock_resolve.return_value = {}

        hits = [
            {"target": "AF-P01541-F1-model_v6 Denclatoxin-B", "eval": 2.168e-05},
            {"target": "AF-Q43226-F1-model_v6 Thionin class 1", "eval": 0.00164},
            # Unresolvable in this test (SIFTS mocked to return None) - must
            # be excluded from ranking entirely, not just left unannotated,
            # so it can't crowd out a resolvable hit further down the list.
            {"target": "1ab1-assembly1.cif.gz_A SI FORM CRAMBIN", "eval": 0.0000001},
        ]

        aggregator = AnnotationAggregator()
        result = await aggregator.aggregate_for_hits(hits, top_n_neighbors=10)

        assert result["neighbors_considered"] == 2
        assert result["total_hit_count"] == 3
        assert result["resolvable_hit_count"] == 2
        assert result["annotated_neighbor_count"] == 2
        assert result["unannotated_neighbor_count"] == 0
        assert result["neighbors_with_interactions_count"] == 0
        assert result["neighbors_with_pathways_count"] == 0
        assert result["top_domains"][0]["name"] == "Thionin"
        assert result["top_domains"][0]["neighbor_count"] == 2
        assert result["top_go_terms"][0]["id"] == "GO:0006952"
        assert result["top_go_terms"][0]["neighbor_count"] == 1

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.resolve_go_term_names")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_reactome_pathways")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_string_partners")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_quickgo_annotations")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_interpro_entries")
    async def test_reports_string_and_reactome_coverage_separately_from_annotated_count(
        self, mock_interpro, mock_quickgo, mock_string, mock_reactome, mock_resolve
    ):
        """STRING/Reactome coverage is real signal but incidental to whether
        a neighbor counts as "annotated" (that's InterPro/QuickGO, which
        cover far more organisms) - verify both are surfaced as their own
        counts rather than silently folded in or dropped."""
        mock_interpro.return_value = []
        mock_quickgo.return_value = []
        mock_string.return_value = [{"partner_name": "SFN", "score": 0.999}]
        mock_reactome.return_value = [{"id": "R-HSA-111448", "name": "Activation of NOXA"}]
        mock_resolve.return_value = {}

        hits = [{"target": "AF-P04637-F1-model_v6 Cellular tumor antigen p53", "eval": 1e-10}]

        aggregator = AnnotationAggregator()
        result = await aggregator.aggregate_for_hits(hits, top_n_neighbors=10)

        assert result["annotated_neighbor_count"] == 0  # no InterPro/QuickGO data
        assert result["neighbors_with_interactions_count"] == 1
        assert result["neighbors_with_pathways_count"] == 1
        assert result["per_neighbor"][0]["string_partners"] == [
            {"partner_name": "SFN", "score": 0.999}
        ]
        assert result["per_neighbor"][0]["reactome_pathways"] == [
            {"id": "R-HSA-111448", "name": "Activation of NOXA"}
        ]

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.resolve_go_term_names")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.resolve_pdb_uniprot_accession")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_reactome_pathways")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_string_partners")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_quickgo_annotations")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_interpro_entries")
    async def test_unresolvable_hits_cannot_crowd_out_resolvable_ones(
        self, mock_interpro, mock_quickgo, mock_string, mock_reactome, mock_pdb_sifts, mock_resolve
    ):
        """Regression test for a real gap found live-testing 1CRN: a wall of
        near-identical PDB100 hits (re-solved structures of the exact same
        protein) can have far lower E-values than every AFDB hit, so ranking
        top_n across ALL hits before filtering left zero annotatable
        neighbors even though good AFDB matches existed. Filtering to
        resolvable hits first fixes this. (PDB hits are mocked as having no
        SIFTS mapping here, to isolate this from the separate PDB-resolution
        feature and its own tests.)"""
        mock_interpro.return_value = [{"accession": "IPR001010", "name": "Thionin", "type": "family", "go_terms": []}]
        mock_quickgo.return_value = []
        mock_string.return_value = []
        mock_reactome.return_value = []
        mock_pdb_sifts.return_value = None
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
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_reactome_pathways")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_string_partners")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_quickgo_annotations")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_interpro_entries")
    async def test_respects_top_n_neighbors_limit(
        self, mock_interpro, mock_quickgo, mock_string, mock_reactome, mock_resolve
    ):
        mock_interpro.return_value = []
        mock_quickgo.return_value = []
        mock_string.return_value = []
        mock_reactome.return_value = []
        mock_resolve.return_value = {}

        hits = [
            {"target": f"AF-P0000{i}-F1-model_v6 X", "eval": i * 0.001} for i in range(5)
        ]

        aggregator = AnnotationAggregator()
        result = await aggregator.aggregate_for_hits(hits, top_n_neighbors=2)

        assert result["neighbors_considered"] == 2
        assert mock_interpro.call_count == 2

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.resolve_go_term_names")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_reactome_pathways")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_string_partners")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_quickgo_annotations")
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_interpro_entries")
    async def test_only_fully_annotates_the_kept_neighbors_not_the_whole_candidate_pool(
        self, mock_interpro, mock_quickgo, mock_string, mock_reactome, mock_resolve
    ):
        """The candidate pool is oversampled (CANDIDATE_OVERSAMPLE_FACTOR x
        top_n_neighbors) so a few unresolvable hits can't starve the
        annotation budget - but once enough hits resolve, the 4 full
        annotation API calls should only run for the top_n_neighbors kept,
        not for every resolved candidate in the larger pool."""
        mock_interpro.return_value = []
        mock_quickgo.return_value = []
        mock_string.return_value = []
        mock_reactome.return_value = []
        mock_resolve.return_value = {}

        # All 10 hits resolve (AFDB format); with top_n_neighbors=2 and the
        # default 2x oversample, the candidate pool is 4, but only the top 2
        # resolved hits should get the full 4-API annotation treatment.
        hits = [
            {"target": f"AF-P0000{i}-F1-model_v6 X", "eval": i * 0.001} for i in range(10)
        ]

        aggregator = AnnotationAggregator()
        result = await aggregator.aggregate_for_hits(hits, top_n_neighbors=2)

        assert result["candidates_examined"] == 4  # 2 * CANDIDATE_OVERSAMPLE_FACTOR
        assert result["resolvable_hit_count"] == 4  # all 4 candidates resolved
        assert result["neighbors_considered"] == 2  # but only top_n_neighbors kept
        assert mock_interpro.call_count == 2  # annotation only fetched for the 2 kept
