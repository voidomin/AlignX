import asyncio
import threading
import time
from unittest.mock import patch, AsyncMock, MagicMock, ANY

import httpx
import pytest

from src.backend.annotation_aggregator import AnnotationAggregator, _RateLimiter


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


class TestRateLimiterConcurrency:
    """_RateLimiter.wait() only ever holds its threading.Lock for the
    synchronous slot-reservation math, never across the actual await - see
    the class docstring for why. These are the two scenarios that would
    break if that invariant regressed: concurrent callers on the SAME
    event loop (aggregate_for_hits() gathers multiple neighbors'
    annotation fetches together, each independently calling
    fetch_string_partners -> wait()) and concurrent callers from
    DIFFERENT threads/event loops (concurrent Discover jobs)."""

    @pytest.mark.asyncio
    async def test_concurrent_waiters_on_same_event_loop_all_complete(self):
        """The scenario that would deadlock if wait() held the lock across
        an await: sleeping while holding self._lock, with a sibling
        gathered coroutine then trying a synchronous (blocking) acquire of
        that same lock on the same thread, freezes the event loop that
        would otherwise have advanced the first caller's timer."""
        limiter = _RateLimiter(min_interval_seconds=0.1)

        results = await asyncio.wait_for(
            asyncio.gather(*(limiter.wait() for _ in range(5))), timeout=5
        )
        assert results == [None] * 5

    def test_concurrent_waiters_from_different_threads_all_complete(self):
        """Mirrors FoldseekClient's cross-thread regression test - a plain
        threading.Lock must keep working correctly when wait() is called
        from several independent asyncio.run() event loops at once."""
        limiter = _RateLimiter(min_interval_seconds=0.1)
        completed = []
        errors = []

        def run_in_thread(name):
            async def go():
                await limiter.wait()

            try:
                asyncio.run(go())
                completed.append(name)
            except Exception as e:
                errors.append((name, e))

        threads = [
            threading.Thread(target=run_in_thread, args=(f"job-{i}",)) for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert not any(t.is_alive() for t in threads), "a waiter thread hung"
        assert errors == []
        assert len(completed) == 5

    @pytest.mark.asyncio
    async def test_successive_waits_are_staggered_by_at_least_min_interval(self):
        limiter = _RateLimiter(min_interval_seconds=0.05)
        start = time.monotonic()
        await limiter.wait()
        await limiter.wait()
        await limiter.wait()
        # Checks the limiter's own reserved slot, not wall-clock time
        # elapsed around the awaits - the latter is flaky under OS
        # scheduler jitter (asyncio.sleep() waking a few ms late/early),
        # while the reservation itself is pure deterministic arithmetic.
        assert limiter._last_request_at >= start + 2 * limiter._min_interval


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


class TestExtractCathPdbChain:

    def test_extracts_pdb_id_and_chain_from_cath_domain_id(self):
        assert AnnotationAggregator.extract_cath_pdb_chain("1cbnA00") == ("1CBN", "A")

    def test_returns_none_for_pdb100_target(self):
        target = "1ab1-assembly1.cif.gz_A SI FORM CRAMBIN"
        assert AnnotationAggregator.extract_cath_pdb_chain(target) is None

    def test_returns_none_for_empty_target(self):
        assert AnnotationAggregator.extract_cath_pdb_chain("") is None


class TestExtractEmbeddedUniprotAccession:

    def test_extracts_from_bfvd_target(self):
        target = "A0A7U0G8Z5_unrelaxed_rank_001_alphafold2_ptm_model_2_seed_000"
        assert (
            AnnotationAggregator.extract_embedded_uniprot_accession(target)
            == "A0A7U0G8Z5"
        )

    def test_extracts_from_bfmd_levylab_target(self):
        target = "LevyLab_Q8U2A3_V1_4_relaxed_B"
        assert (
            AnnotationAggregator.extract_embedded_uniprot_accession(target) == "Q8U2A3"
        )

    def test_extracts_first_accession_from_bfmd_variant_pair_target(self):
        target = "ProtVar_P08559_Q9Y6H1_B"
        assert (
            AnnotationAggregator.extract_embedded_uniprot_accession(target) == "P08559"
        )

    def test_extracts_short_form_accession(self):
        target = "R4T7Q6_unrelaxed_rank_001_alphafold2_ptm_model_2_seed_000"
        assert (
            AnnotationAggregator.extract_embedded_uniprot_accession(target) == "R4T7Q6"
        )

    def test_returns_none_for_gmgc_target(self):
        target = "GMGC10.211_012_347.UNKNOWN_trun_1.pdb"
        assert AnnotationAggregator.extract_embedded_uniprot_accession(target) is None

    def test_returns_none_for_mgnify_esm_atlas_target(self):
        assert (
            AnnotationAggregator.extract_embedded_uniprot_accession(
                "MGYP001043648370.pdb.gz"
            )
            is None
        )

    def test_returns_none_for_uniparc_id(self):
        # UPI-prefixed UniParc IDs aren't UniProt accessions - a real hit
        # seen in a live BFVD/mgnify_esm30 query, must not false-positive.
        target = "UPI001E6A929D_unrelaxed_rank_001_alphafold2_ptm_model_2_seed_000"
        assert AnnotationAggregator.extract_embedded_uniprot_accession(target) is None

    def test_returns_none_for_empty_target(self):
        assert AnnotationAggregator.extract_embedded_uniprot_accession("") is None


class TestExtractGmgcGeneId:

    def test_extracts_gene_id_with_unknown_name(self):
        target = "GMGC10.211_012_347.UNKNOWN_trun_1.pdb"
        assert (
            AnnotationAggregator.extract_gmgc_gene_id(target)
            == "GMGC10.211_012_347.UNKNOWN"
        )

    def test_extracts_gene_id_with_named_annotation(self):
        target = "GMGC10.040_893_565.PILY1_trun_2.pdb"
        assert (
            AnnotationAggregator.extract_gmgc_gene_id(target)
            == "GMGC10.040_893_565.PILY1"
        )

    def test_handles_underscore_in_gene_name(self):
        # GMGC's own docs show names like "SCLAV_5304" that themselves
        # contain an underscore - must not be confused with the "_trun_N"
        # suffix and truncated early.
        target = "GMGC10.054_598_380.SCLAV_5304_trun_0.pdb"
        assert (
            AnnotationAggregator.extract_gmgc_gene_id(target)
            == "GMGC10.054_598_380.SCLAV_5304"
        )

    def test_returns_none_for_non_gmgc_target(self):
        target = "AF-P01541-F1-model_v6 Denclatoxin-B"
        assert AnnotationAggregator.extract_gmgc_gene_id(target) is None

    def test_returns_none_for_mgnify_esm_atlas_target(self):
        assert (
            AnnotationAggregator.extract_gmgc_gene_id("MGYP001043648370.pdb.gz") is None
        )

    def test_returns_none_for_empty_target(self):
        assert AnnotationAggregator.extract_gmgc_gene_id("") is None


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
            {
                "id": "GO:0006952",
                "name": "defense response",
                "aspect": "biological_process",
            }
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
    async def test_returns_empty_on_http_error(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("no route")
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            entries = await aggregator.fetch_interpro_entries("P01541", client)
        assert entries == []

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_second_call_for_same_accession_uses_cache_not_network(
        self, mock_get
    ):
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

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_returns_empty_on_non_200(self, mock_get):
        mock_get.return_value = _mock_response(status_code=404)
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            terms = await aggregator.fetch_quickgo_annotations("NOPE", client)
        assert terms == []

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_returns_empty_on_http_error(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("no route")
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            terms = await aggregator.fetch_quickgo_annotations("P01541", client)
        assert terms == []


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

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.post")
    async def test_returns_empty_when_error_dict_returned(self, mock_post):
        """STRING's error response is actually a bare dict (not
        list-wrapped), unlike the successful-response list of partners -
        this is the real shape the isinstance(payload, dict) check guards
        against."""
        aggregator = AnnotationAggregator()
        mock_post.return_value = _mock_response(json_data={"Error": "unknown organism"})
        async with httpx.AsyncClient() as client:
            partners = await aggregator.fetch_string_partners("P01541", 3965, client)
        assert partners == []

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.post")
    async def test_returns_empty_on_non_200(self, mock_post):
        aggregator = AnnotationAggregator()
        mock_post.return_value = _mock_response(status_code=500)
        async with httpx.AsyncClient() as client:
            partners = await aggregator.fetch_string_partners("P04637", 9606, client)
        assert partners == []

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.post")
    async def test_returns_empty_on_http_error(self, mock_post):
        aggregator = AnnotationAggregator()
        mock_post.side_effect = httpx.ConnectError("no route")
        async with httpx.AsyncClient() as client:
            partners = await aggregator.fetch_string_partners("P04637", 9606, client)
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

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_returns_empty_on_http_error(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("no route")
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            pathways = await aggregator.fetch_reactome_pathways("P04637", client)
        assert pathways == []


class TestFetchGmgcFeatures:

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_parses_pfam_domains(self, mock_get):
        mock_get.return_value = _mock_response(
            json_data={
                "features": {
                    "pfam": [
                        {
                            "domain": "Pfam:Neisseria_PilC",
                            "evalue": 6.6e-49,
                            "bitscore": 165.1,
                        },
                    ],
                    "eggnog": {"predicted_protein_name": "pilY1"},
                }
            }
        )
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            domains = await aggregator.fetch_gmgc_features(
                "GMGC10.040_893_565.PILY1", client
            )

        assert domains == [
            {
                "accession": "Neisseria_PilC",
                "name": "Neisseria_PilC",
                "type": "pfam",
                "go_terms": [],
            },
        ]

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_returns_empty_when_no_pfam_hits(self, mock_get):
        mock_get.return_value = _mock_response(
            json_data={"features": {"eggnog": {"go_terms": []}}}
        )
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            domains = await aggregator.fetch_gmgc_features(
                "GMGC10.211_012_347.UNKNOWN", client
            )
        assert domains == []

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_returns_empty_on_non_200(self, mock_get):
        mock_get.return_value = _mock_response(status_code=404)
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            domains = await aggregator.fetch_gmgc_features(
                "GMGC10.nonexistent.X", client
            )
        assert domains == []

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_returns_empty_on_http_error(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("no route")
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            domains = await aggregator.fetch_gmgc_features(
                "GMGC10.040_893_565.PILY1", client
            )
        assert domains == []


class TestGoTermNameCaching:
    def test_try_get_cached_go_name_returns_none_without_cache_db(self):
        aggregator = AnnotationAggregator()
        assert aggregator._try_get_cached_go_name("GO:0005515") is None

    def test_try_get_cached_go_name_returns_cached_value(self):
        cache_db = MagicMock()
        cache_db.get_annotation_cache.return_value = '"protein binding"'
        aggregator = AnnotationAggregator(cache_db=cache_db)

        assert aggregator._try_get_cached_go_name("GO:0005515") == "protein binding"

    def test_try_get_cached_go_name_returns_none_on_cache_miss(self):
        cache_db = MagicMock()
        cache_db.get_annotation_cache.return_value = None
        aggregator = AnnotationAggregator(cache_db=cache_db)

        assert aggregator._try_get_cached_go_name("GO:0005515") is None

    def test_try_get_cached_go_name_swallows_cache_read_errors(self):
        cache_db = MagicMock()
        cache_db.get_annotation_cache.side_effect = Exception("db locked")
        aggregator = AnnotationAggregator(cache_db=cache_db)

        assert aggregator._try_get_cached_go_name("GO:0005515") is None

    def test_try_cache_go_name_noop_without_cache_db(self):
        aggregator = AnnotationAggregator()
        # Should not raise even though there's nothing to write to.
        aggregator._try_cache_go_name("GO:0005515", "protein binding")

    def test_try_cache_go_name_writes_through_cache_db(self):
        cache_db = MagicMock()
        aggregator = AnnotationAggregator(cache_db=cache_db)

        aggregator._try_cache_go_name("GO:0005515", "protein binding")

        cache_db.set_annotation_cache.assert_called_once_with(
            "goterm:GO:0005515", "goterm", '"protein binding"'
        )

    def test_try_cache_go_name_swallows_cache_write_errors(self):
        cache_db = MagicMock()
        cache_db.set_annotation_cache.side_effect = Exception("disk full")
        aggregator = AnnotationAggregator(cache_db=cache_db)

        # Should not raise.
        aggregator._try_cache_go_name("GO:0005515", "protein binding")


class TestFetchGoTermNamesChunk:
    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_returns_names_and_caches_them(self, mock_get):
        mock_get.return_value = _mock_response(
            json_data={
                "results": [
                    {"id": "GO:0005515", "name": "protein binding"},
                    {"id": "GO:0006412", "name": "translation"},
                ]
            }
        )
        cache_db = MagicMock()
        aggregator = AnnotationAggregator(cache_db=cache_db)

        async with httpx.AsyncClient() as client:
            names = await aggregator._fetch_go_term_names_chunk(
                ["GO:0005515", "GO:0006412"], client
            )

        assert names == {
            "GO:0005515": "protein binding",
            "GO:0006412": "translation",
        }
        assert cache_db.set_annotation_cache.call_count == 2

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_returns_empty_on_non_200(self, mock_get):
        mock_get.return_value = _mock_response(status_code=500)
        aggregator = AnnotationAggregator()

        async with httpx.AsyncClient() as client:
            names = await aggregator._fetch_go_term_names_chunk(["GO:0005515"], client)

        assert names == {}

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_returns_empty_on_http_error(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("no route")
        aggregator = AnnotationAggregator()

        async with httpx.AsyncClient() as client:
            names = await aggregator._fetch_go_term_names_chunk(["GO:0005515"], client)

        assert names == {}

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_skips_results_missing_id_or_name(self, mock_get):
        mock_get.return_value = _mock_response(
            json_data={"results": [{"id": "GO:0005515"}, {"name": "orphan name"}]}
        )
        aggregator = AnnotationAggregator()

        async with httpx.AsyncClient() as client:
            names = await aggregator._fetch_go_term_names_chunk(["GO:0005515"], client)

        assert names == {}


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
            accession = await aggregator.resolve_pdb_uniprot_accession(
                "1CRN", "A", client
            )
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
            accession = await aggregator.resolve_pdb_uniprot_accession(
                "1ABC", "A", client
            )
        assert accession is None

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_returns_none_on_non_200(self, mock_get):
        mock_get.return_value = _mock_response(status_code=404)
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            accession = await aggregator.resolve_pdb_uniprot_accession(
                "ZZZZ", "A", client
            )
        assert accession is None

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_returns_none_on_http_error(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("no route")
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            accession = await aggregator.resolve_pdb_uniprot_accession(
                "1CRN", "A", client
            )
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
            first = await aggregator.resolve_pdb_uniprot_accession(
                "1CRN", "A", client, cache
            )
            second = await aggregator.resolve_pdb_uniprot_accession(
                "1CRN", "A", client, cache
            )

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

    @pytest.mark.asyncio
    async def test_returns_none_for_gmgc_target(self):
        aggregator = AnnotationAggregator()
        hit = {"target": "GMGC10.211_012_347.UNKNOWN_trun_1.pdb"}
        async with httpx.AsyncClient() as client:
            accession = await aggregator.resolve_accession(hit, client)
        assert accession is None

    @pytest.mark.asyncio
    async def test_returns_none_for_mgnify_esm_atlas_target(self):
        aggregator = AnnotationAggregator()
        hit = {"target": "MGYP001043648370.pdb.gz"}
        async with httpx.AsyncClient() as client:
            accession = await aggregator.resolve_accession(hit, client)
        assert accession is None

    @pytest.mark.asyncio
    async def test_resolves_bfvd_target_via_embedded_accession(self):
        aggregator = AnnotationAggregator()
        with patch.object(
            aggregator, "resolve_pdb_uniprot_accession", new_callable=AsyncMock
        ) as mock_sifts:
            hit = {
                "target": "A0A7U0G8Z5_unrelaxed_rank_001_alphafold2_ptm_model_2_seed_000"
            }
            async with httpx.AsyncClient() as client:
                accession = await aggregator.resolve_accession(hit, client)
            assert accession == "A0A7U0G8Z5"
            mock_sifts.assert_not_called()

    @pytest.mark.asyncio
    async def test_resolves_bfmd_target_via_embedded_accession(self):
        aggregator = AnnotationAggregator()
        hit = {"target": "LevyLab_Q8U2A3_V1_4_relaxed_B"}
        async with httpx.AsyncClient() as client:
            accession = await aggregator.resolve_accession(hit, client)
        assert accession == "Q8U2A3"

    @pytest.mark.asyncio
    async def test_falls_back_to_sifts_for_cath_domain_targets(self):
        aggregator = AnnotationAggregator()
        with patch.object(
            aggregator, "resolve_pdb_uniprot_accession", new_callable=AsyncMock
        ) as mock_sifts:
            mock_sifts.return_value = "P01542"
            hit = {"target": "1cbnA00"}
            async with httpx.AsyncClient() as client:
                accession = await aggregator.resolve_accession(hit, client)
            assert accession == "P01542"
            mock_sifts.assert_called_once_with("1CBN", "A", client, None)


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

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_uses_cached_name_without_fetching_that_id(self, mock_get):
        cache_db = MagicMock()
        cache_db.get_annotation_cache.side_effect = lambda key, *a, **k: (
            '"cached name"' if "GO:0001" in key else None
        )
        mock_get.return_value = _mock_response(
            json_data={"results": [{"id": "GO:0002", "name": "fetched name"}]}
        )
        aggregator = AnnotationAggregator(cache_db=cache_db)

        async with httpx.AsyncClient() as client:
            names = await aggregator.resolve_go_term_names(
                ["GO:0001", "GO:0002"], client
            )

        assert names == {"GO:0001": "cached name", "GO:0002": "fetched name"}
        # Only the uncached id should have been requested over the network.
        requested_ids = mock_get.call_args[0][0]
        assert "GO:0001" not in requested_ids
        assert "GO:0002" in requested_ids


class TestResolveStructureAccession:
    @pytest.mark.asyncio
    async def test_alphafold_source_uses_the_free_regex_no_http_call(self):
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            accession = await aggregator._resolve_structure_accession(
                "AF-P69905-F1", None, "alphafold", client, None
            )
        assert accession == "P69905"

    @pytest.mark.asyncio
    async def test_swissmodel_source_splits_the_id_no_http_call(self):
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            accession = await aggregator._resolve_structure_accession(
                "SM-P12345", None, "swissmodel", client, None
            )
        assert accession == "P12345"

    @pytest.mark.asyncio
    async def test_esmfold_source_returns_none_no_http_call(self):
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            accession = await aggregator._resolve_structure_accession(
                "ESM-MGYP002537940442", "A", "esmfold", client, None
            )
        assert accession is None

    @pytest.mark.asyncio
    async def test_pdb_source_without_a_chain_returns_none(self):
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            accession = await aggregator._resolve_structure_accession(
                "1CRN", None, "pdb", client, None
            )
        assert accession is None

    @pytest.mark.asyncio
    @patch("src.backend.annotation_aggregator.httpx.AsyncClient.get")
    async def test_pdb_source_with_a_chain_does_a_real_sifts_lookup(self, mock_get):
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
        async with httpx.AsyncClient() as client:
            accession = await aggregator._resolve_structure_accession(
                "1CRN", "A", "pdb", client, None
            )
        assert accession == "P01542"
        mock_get.assert_called_once()


class TestAggregateForStructure:
    @pytest.mark.asyncio
    async def test_unresolvable_accession_returns_empty_annotation_no_fetch_calls(self):
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            result = await aggregator.aggregate_for_structure(
                "ESM-MGYP002537940442", "A", "esmfold", client
            )
        assert result == {
            "pdb_id": "ESM-MGYP002537940442",
            "chain": "A",
            "accession": None,
            "domains": [],
            "go_terms": [],
            "reactome_pathways": [],
        }

    @pytest.mark.asyncio
    async def test_resolved_accession_fetches_domains_go_terms_and_pathways(self):
        aggregator = AnnotationAggregator()
        with patch.object(
            aggregator, "_resolve_structure_accession", AsyncMock(return_value="P69905")
        ), patch.object(
            aggregator,
            "fetch_interpro_entries",
            AsyncMock(
                return_value=[
                    {
                        "accession": "IPR000971",
                        "name": "Globin",
                        "type": "domain",
                        "go_terms": [],
                    }
                ]
            ),
        ), patch.object(
            aggregator,
            "fetch_quickgo_annotations",
            AsyncMock(
                return_value=[
                    {
                        "id": "GO:0005344",
                        "aspect": "F",
                        "qualifier": None,
                        "evidence": "IDA",
                    }
                ]
            ),
        ), patch.object(
            aggregator,
            "fetch_reactome_pathways",
            AsyncMock(
                return_value=[
                    {"id": "R-HSA-1247673", "name": "Erythrocytes take up oxygen"}
                ]
            ),
        ), patch.object(
            aggregator,
            "resolve_go_term_names",
            AsyncMock(return_value={"GO:0005344": "oxygen carrier activity"}),
        ):
            async with httpx.AsyncClient() as client:
                result = await aggregator.aggregate_for_structure(
                    "AF-P69905-F1", None, "alphafold", client
                )

        assert result["accession"] == "P69905"
        assert result["domains"][0]["name"] == "Globin"
        assert result["go_terms"][0]["name"] == "oxygen carrier activity"
        assert result["reactome_pathways"][0]["name"] == "Erythrocytes take up oxygen"

    @pytest.mark.asyncio
    async def test_pdb_id_and_chain_pass_through_to_the_result(self):
        aggregator = AnnotationAggregator()
        async with httpx.AsyncClient() as client:
            result = await aggregator.aggregate_for_structure(
                "4HHB", "A", "pdb", client
            )
        assert result["pdb_id"] == "4HHB"
        assert result["chain"] == "A"

    @pytest.mark.asyncio
    async def test_go_terms_are_deduplicated_by_id(self):
        """Regression: QuickGO's annotation-search returns one row per
        curated evidence code, so a common term like "protein binding" can
        appear many times for the same accession - real duplicate records,
        not a fetch bug. Caught via live manual verification (a real
        hemoglobin lookup showed "protein binding" six times in a row)."""
        aggregator = AnnotationAggregator()
        with patch.object(
            aggregator, "_resolve_structure_accession", AsyncMock(return_value="P69905")
        ), patch.object(
            aggregator, "fetch_interpro_entries", AsyncMock(return_value=[])
        ), patch.object(
            aggregator,
            "fetch_quickgo_annotations",
            AsyncMock(
                return_value=[
                    {"id": "GO:0005515", "aspect": "F", "evidence": "IPI"},
                    {"id": "GO:0005515", "aspect": "F", "evidence": "IEA"},
                    {"id": "GO:0005515", "aspect": "F", "evidence": "IBA"},
                    {"id": "GO:0020037", "aspect": "F", "evidence": "IDA"},
                ]
            ),
        ), patch.object(
            aggregator, "fetch_reactome_pathways", AsyncMock(return_value=[])
        ), patch.object(
            aggregator,
            "resolve_go_term_names",
            AsyncMock(
                return_value={
                    "GO:0005515": "protein binding",
                    "GO:0020037": "heme binding",
                }
            ),
        ):
            async with httpx.AsyncClient() as client:
                result = await aggregator.aggregate_for_structure(
                    "AF-P69905-F1", None, "alphafold", client
                )

        ids = [g["id"] for g in result["go_terms"]]
        assert ids == ["GO:0005515", "GO:0020037"]


class TestHitSortKey:
    def test_prefers_eval_key(self):
        assert AnnotationAggregator._hit_sort_key({"eval": "1e-10"}) == pytest.approx(
            1e-10
        )

    def test_falls_back_to_default_on_unparseable_value(self):
        assert AnnotationAggregator._hit_sort_key({"eval": "not-a-number"}) == 1e9

    def test_falls_back_to_default_when_no_key_present(self):
        assert AnnotationAggregator._hit_sort_key({}) == 1e9


class TestAggregateForHits:

    @pytest.mark.asyncio
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.resolve_go_term_names"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.resolve_pdb_uniprot_accession"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_reactome_pathways"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_string_partners"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_quickgo_annotations"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_interpro_entries"
    )
    async def test_aggregates_domains_and_go_terms_across_neighbors(
        self,
        mock_interpro,
        mock_quickgo,
        mock_string,
        mock_reactome,
        mock_pdb_sifts,
        mock_resolve,
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

        def quickgo_side_effect(accession, client):
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
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.resolve_go_term_names"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_reactome_pathways"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_string_partners"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_quickgo_annotations"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_interpro_entries"
    )
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
        mock_reactome.return_value = [
            {"id": "R-HSA-111448", "name": "Activation of NOXA"}
        ]
        mock_resolve.return_value = {}

        hits = [
            {
                "target": "AF-P04637-F1-model_v6 Cellular tumor antigen p53",
                "eval": 1e-10,
            }
        ]

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
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.resolve_go_term_names"
    )
    @patch("src.backend.annotation_aggregator.AnnotationAggregator.fetch_gmgc_features")
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_reactome_pathways"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_string_partners"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_quickgo_annotations"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_interpro_entries"
    )
    async def test_gmgc_hit_with_no_uniprot_accession_still_gets_annotated(
        self,
        mock_interpro,
        mock_quickgo,
        mock_string,
        mock_reactome,
        mock_gmgc,
        mock_resolve,
    ):
        """A gmgcl_id hit has no UniProt accession at all - unlike every
        other resolvable database - so it must never reach the UniProt-based
        fetches, only fetch_gmgc_features."""
        mock_interpro.return_value = []
        mock_quickgo.return_value = []
        mock_string.return_value = []
        mock_reactome.return_value = []
        mock_gmgc.return_value = [
            {
                "accession": "Neisseria_PilC",
                "name": "Neisseria_PilC",
                "type": "pfam",
                "go_terms": [],
            }
        ]
        mock_resolve.return_value = {}

        hits = [
            {
                "target": "GMGC10.040_893_565.PILY1_trun_2.pdb",
                "eval": 1e-49,
                "prob": 0.9,
            }
        ]

        aggregator = AnnotationAggregator()
        result = await aggregator.aggregate_for_hits(hits, top_n_neighbors=10)

        mock_gmgc.assert_called_once_with("GMGC10.040_893_565.PILY1", ANY)
        mock_interpro.assert_not_called()
        mock_quickgo.assert_not_called()
        assert result["resolvable_hit_count"] == 1
        assert result["annotated_neighbor_count"] == 1
        assert result["top_domains"][0]["name"] == "Neisseria_PilC"
        assert result["top_domains"][0]["type"] == "pfam"

    @pytest.mark.asyncio
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.resolve_go_term_names"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.resolve_pdb_uniprot_accession"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_reactome_pathways"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_string_partners"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_quickgo_annotations"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_interpro_entries"
    )
    async def test_unresolvable_hits_cannot_crowd_out_resolvable_ones(
        self,
        mock_interpro,
        mock_quickgo,
        mock_string,
        mock_reactome,
        mock_pdb_sifts,
        mock_resolve,
    ):
        """Regression test for a real gap found live-testing 1CRN: a wall of
        near-identical PDB100 hits (re-solved structures of the exact same
        protein) can have far lower E-values than every AFDB hit, so ranking
        top_n across ALL hits before filtering left zero annotatable
        neighbors even though good AFDB matches existed. Filtering to
        resolvable hits first fixes this. (PDB hits are mocked as having no
        SIFTS mapping here, to isolate this from the separate PDB-resolution
        feature and its own tests.)"""
        mock_interpro.return_value = [
            {
                "accession": "IPR001010",
                "name": "Thionin",
                "type": "family",
                "go_terms": [],
            }
        ]
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
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.resolve_go_term_names"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_reactome_pathways"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_string_partners"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_quickgo_annotations"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_interpro_entries"
    )
    async def test_respects_top_n_neighbors_limit(
        self, mock_interpro, mock_quickgo, mock_string, mock_reactome, mock_resolve
    ):
        mock_interpro.return_value = []
        mock_quickgo.return_value = []
        mock_string.return_value = []
        mock_reactome.return_value = []
        mock_resolve.return_value = {}

        hits = [
            {"target": f"AF-P0000{i}-F1-model_v6 X", "eval": i * 0.001}
            for i in range(5)
        ]

        aggregator = AnnotationAggregator()
        result = await aggregator.aggregate_for_hits(hits, top_n_neighbors=2)

        assert result["neighbors_considered"] == 2
        assert mock_interpro.call_count == 2

    @pytest.mark.asyncio
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.resolve_go_term_names"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_reactome_pathways"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_string_partners"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_quickgo_annotations"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_interpro_entries"
    )
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
            {"target": f"AF-P0000{i}-F1-model_v6 X", "eval": i * 0.001}
            for i in range(10)
        ]

        aggregator = AnnotationAggregator()
        result = await aggregator.aggregate_for_hits(hits, top_n_neighbors=2)

        assert result["candidates_examined"] == 4  # 2 * CANDIDATE_OVERSAMPLE_FACTOR
        assert result["resolvable_hit_count"] == 4  # all 4 candidates resolved
        assert result["neighbors_considered"] == 2  # but only top_n_neighbors kept
        assert mock_interpro.call_count == 2  # annotation only fetched for the 2 kept

    @pytest.mark.asyncio
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.resolve_go_term_names"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_reactome_pathways"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_string_partners"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_quickgo_annotations"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_interpro_entries"
    )
    async def test_confidence_gate_excludes_low_probability_matches_from_hypothesis(
        self, mock_interpro, mock_quickgo, mock_string, mock_reactome, mock_resolve
    ):
        """Having curated annotations isn't enough on its own to state a
        function hypothesis if the structural match itself was weak - a
        neighbor only counts toward high_confidence_annotated_count (and
        the high_confidence_top_* lists) if its own Foldseek prob also
        clears min_confident_probability."""
        mock_interpro.return_value = [
            {
                "accession": "IPR001010",
                "name": "Thionin",
                "type": "family",
                "go_terms": [],
            }
        ]
        mock_quickgo.return_value = []
        mock_string.return_value = []
        mock_reactome.return_value = []
        mock_resolve.return_value = {}

        hits = [
            {
                "target": "AF-P01541-F1-model_v6 High confidence",
                "eval": 1e-10,
                "prob": 0.95,
            },
            {
                "target": "AF-Q43226-F1-model_v6 Low confidence",
                "eval": 0.01,
                "prob": 0.2,
            },
        ]

        aggregator = AnnotationAggregator()
        result = await aggregator.aggregate_for_hits(hits, top_n_neighbors=10)

        assert result["annotated_neighbor_count"] == 2  # both got InterPro data
        assert result["high_confidence_annotated_count"] == 1  # only the prob=0.95 one
        assert result["min_confident_probability"] == pytest.approx(0.5)
        assert len(result["top_domains"]) == 1
        assert result["top_domains"][0]["neighbor_count"] == 2  # unfiltered: both count
        assert len(result["high_confidence_top_domains"]) == 1
        assert (
            result["high_confidence_top_domains"][0]["neighbor_count"] == 1
        )  # filtered: only 1

    @pytest.mark.asyncio
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.resolve_go_term_names"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_reactome_pathways"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_string_partners"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_quickgo_annotations"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_interpro_entries"
    )
    async def test_confidence_gate_respects_custom_threshold_from_config(
        self, mock_interpro, mock_quickgo, mock_string, mock_reactome, mock_resolve
    ):
        mock_interpro.return_value = [
            {
                "accession": "IPR001010",
                "name": "Thionin",
                "type": "family",
                "go_terms": [],
            }
        ]
        mock_quickgo.return_value = []
        mock_string.return_value = []
        mock_reactome.return_value = []
        mock_resolve.return_value = {}

        hits = [{"target": "AF-P01541-F1-model_v6 X", "eval": 1e-10, "prob": 0.6}]

        strict_aggregator = AnnotationAggregator(
            config={"annotation": {"min_confident_probability": 0.9}}
        )
        strict_result = await strict_aggregator.aggregate_for_hits(
            hits, top_n_neighbors=10
        )
        assert strict_result["high_confidence_annotated_count"] == 0

        lenient_aggregator = AnnotationAggregator(
            config={"annotation": {"min_confident_probability": 0.5}}
        )
        lenient_result = await lenient_aggregator.aggregate_for_hits(
            hits, top_n_neighbors=10
        )
        assert lenient_result["high_confidence_annotated_count"] == 1

    @pytest.mark.asyncio
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.resolve_go_term_names"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_reactome_pathways"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_string_partners"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_quickgo_annotations"
    )
    @patch(
        "src.backend.annotation_aggregator.AnnotationAggregator.fetch_interpro_entries"
    )
    async def test_confidence_gate_treats_missing_prob_as_unconfident(
        self, mock_interpro, mock_quickgo, mock_string, mock_reactome, mock_resolve
    ):
        """A hit with no prob field at all (e.g. a malformed/non-standard
        Foldseek response) must not silently count as confident."""
        mock_interpro.return_value = [
            {
                "accession": "IPR001010",
                "name": "Thionin",
                "type": "family",
                "go_terms": [],
            }
        ]
        mock_quickgo.return_value = []
        mock_string.return_value = []
        mock_reactome.return_value = []
        mock_resolve.return_value = {}

        hits = [{"target": "AF-P01541-F1-model_v6 X", "eval": 1e-10}]  # no "prob" key

        aggregator = AnnotationAggregator()
        result = await aggregator.aggregate_for_hits(hits, top_n_neighbors=10)

        assert result["annotated_neighbor_count"] == 1
        assert result["high_confidence_annotated_count"] == 0
