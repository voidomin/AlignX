from unittest.mock import patch, AsyncMock, MagicMock

import httpx
import pytest

from src.backend.blast_client import BlastClient, BlastError


@pytest.fixture(autouse=True)
def fast_rate_limiter():
    """The real rate limiter enforces a 3s gap between submit/fetch calls,
    which would make every test slow. Zero it out for the duration of
    these tests."""
    original = BlastClient._rate_limiter._min_interval
    BlastClient._rate_limiter._min_interval = 0
    BlastClient._rate_limiter._last_request_at = 0.0
    yield
    BlastClient._rate_limiter._min_interval = original


def _text_response(text):
    response = AsyncMock()
    response.raise_for_status = MagicMock()
    response.text = text
    return response


_REAL_LOOKING_XML = """<?xml version="1.0"?>
<BlastOutput>
  <BlastOutput_iterations>
    <Iteration>
      <Iteration_hits>
        <Hit>
          <Hit_accession>NP_000509</Hit_accession>
          <Hit_def>hemoglobin subunit beta [Homo sapiens]</Hit_def>
          <Hit_hsps>
            <Hsp>
              <Hsp_query-from>1</Hsp_query-from>
              <Hsp_qseq>MVHLTPEEK</Hsp_qseq>
              <Hsp_hseq>MVHLTPEEK</Hsp_hseq>
            </Hsp>
          </Hit_hsps>
        </Hit>
        <Hit>
          <Hit_accession>XP_012345</Hit_accession>
          <Hit_def>hemoglobin subunit beta-like [Some organism]</Hit_def>
          <Hit_hsps>
            <Hsp>
              <Hsp_query-from>1</Hsp_query-from>
              <Hsp_qseq>MVHLTPEEK</Hsp_qseq>
              <Hsp_hseq>MVHLSPADK</Hsp_hseq>
            </Hsp>
          </Hit_hsps>
        </Hit>
      </Iteration_hits>
    </Iteration>
  </BlastOutput_iterations>
</BlastOutput>"""


class TestParseHitsXml:
    def test_parses_real_looking_hits(self):
        hits = BlastClient.parse_hits_xml(_REAL_LOOKING_XML)
        assert len(hits) == 2
        assert hits[0]["accession"] == "NP_000509"
        assert hits[0]["qseq"] == "MVHLTPEEK"
        assert hits[0]["hseq"] == "MVHLTPEEK"
        assert hits[0]["query_from"] == 1

    def test_returns_empty_list_on_malformed_xml(self):
        assert BlastClient.parse_hits_xml("not xml at all <<<") == []

    def test_skips_a_hit_with_no_hsp(self):
        xml = """<BlastOutput><BlastOutput_iterations><Iteration>
        <Iteration_hits><Hit><Hit_accession>X</Hit_accession>
        <Hit_hsps></Hit_hsps></Hit></Iteration_hits>
        </Iteration></BlastOutput_iterations></BlastOutput>"""
        assert BlastClient.parse_hits_xml(xml) == []


class TestBuildConservationProfile:
    def test_fully_conserved_column_scores_one(self):
        hits = [
            {"qseq": "MVH", "hseq": "MVH", "query_from": 1},
            {"qseq": "MVH", "hseq": "MVH", "query_from": 1},
        ]
        profile = BlastClient.build_conservation_profile(3, hits)
        assert all(p["conservation"] == pytest.approx(1.0) for p in profile)
        assert profile[0]["most_common"] == "M"

    def test_maximally_diverse_column_scores_near_zero(self):
        # 20 hits, each a different one of the 20 amino acids at position 1 -
        # true maximum-entropy column (log2(20) bits), so conservation -> 0.
        amino_acids = "ACDEFGHIKLMNPQRSTVWY"
        hits = [{"qseq": "M", "hseq": aa, "query_from": 1} for aa in amino_acids]
        profile = BlastClient.build_conservation_profile(1, hits)
        assert profile[0]["conservation"] == pytest.approx(0.0, abs=1e-9)

    def test_position_with_no_covering_hit_gets_none(self):
        hits = [{"qseq": "MV", "hseq": "MV", "query_from": 1}]
        profile = BlastClient.build_conservation_profile(5, hits)
        assert profile[0]["conservation"] is not None
        assert profile[4]["conservation"] is None
        assert profile[4]["num_homologs"] == 0

    def test_internal_gap_in_query_does_not_advance_position(self):
        # A homolog with an insertion relative to the query (query has a gap
        # at that alignment column) must not shift subsequent query
        # positions - only real query residues advance `pos`.
        hits = [{"qseq": "M-VH", "hseq": "MXVH", "query_from": 1}]
        profile = BlastClient.build_conservation_profile(3, hits)
        assert profile[0]["most_common"] == "M"
        assert profile[1]["most_common"] == "V"
        assert profile[2]["most_common"] == "H"

    def test_gap_in_homolog_is_excluded_from_residue_counts(self):
        hits = [
            {"qseq": "MV", "hseq": "M-", "query_from": 1},
            {"qseq": "MV", "hseq": "MV", "query_from": 1},
        ]
        profile = BlastClient.build_conservation_profile(2, hits)
        # Position 2: one real residue (V) and one gap - gap excluded, so
        # this column is still fully conserved among the residues observed.
        assert profile[1]["conservation"] == pytest.approx(1.0)
        assert profile[1]["num_homologs"] == 2

    def test_no_hits_returns_all_none(self):
        profile = BlastClient.build_conservation_profile(3, [])
        assert all(p["conservation"] is None for p in profile)

    def test_residue_counts_preserves_full_distribution_not_just_the_winner(self):
        hits = [
            {"qseq": "M", "hseq": "M", "query_from": 1},
            {"qseq": "M", "hseq": "M", "query_from": 1},
            {"qseq": "M", "hseq": "L", "query_from": 1},
        ]
        profile = BlastClient.build_conservation_profile(1, hits)
        assert profile[0]["most_common"] == "M"
        assert profile[0]["residue_counts"] == {"M": 2, "L": 1}

    def test_residue_counts_is_empty_dict_when_no_hit_covers_the_position(self):
        profile = BlastClient.build_conservation_profile(3, [])
        assert all(p["residue_counts"] == {} for p in profile)


class TestSubmitSearch:
    @pytest.mark.asyncio
    @patch("src.backend.blast_client.httpx.AsyncClient.post")
    async def test_parses_real_looking_rid_and_rtoe(self, mock_post):
        mock_post.return_value = _text_response(
            "stuff before\nRID = 5FUFR8MX014\nRTOE = 36\nstuff after"
        )
        client = BlastClient()
        result = await client.submit_search("MVHL")
        assert result == {"rid": "5FUFR8MX014", "rtoe": 36}

    @pytest.mark.asyncio
    @patch("src.backend.blast_client.httpx.AsyncClient.post")
    async def test_raises_when_no_rid_found(self, mock_post):
        mock_post.return_value = _text_response("no RID here")
        client = BlastClient()
        with pytest.raises(BlastError, match="did not return a request ID"):
            await client.submit_search("MVHL")

    @pytest.mark.asyncio
    @patch("src.backend.blast_client.httpx.AsyncClient.post")
    async def test_wraps_http_errors(self, mock_post):
        mock_post.side_effect = httpx.ConnectError("no route")
        client = BlastClient()
        with pytest.raises(BlastError, match="submission failed"):
            await client.submit_search("MVHL")


class TestPollUntilComplete:
    @pytest.mark.asyncio
    @patch("src.backend.blast_client.httpx.AsyncClient.get")
    async def test_returns_on_ready(self, mock_get):
        mock_get.return_value = _text_response("Status=READY")
        client = BlastClient()
        await client.poll_until_complete("rid-1")
        mock_get.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.backend.blast_client.asyncio.sleep", new_callable=AsyncMock)
    @patch("src.backend.blast_client.httpx.AsyncClient.get")
    async def test_waits_the_initial_rtoe_before_first_poll(self, mock_get, mock_sleep):
        mock_get.return_value = _text_response("Status=READY")
        client = BlastClient()
        await client.poll_until_complete("rid-1", initial_wait_seconds=36)
        mock_sleep.assert_any_call(36)

    @pytest.mark.asyncio
    @patch("src.backend.blast_client.asyncio.sleep", new_callable=AsyncMock)
    @patch("src.backend.blast_client.httpx.AsyncClient.get")
    async def test_keeps_polling_while_waiting(self, mock_get, mock_sleep):
        mock_get.side_effect = [
            _text_response("Status=WAITING"),
            _text_response("Status=WAITING"),
            _text_response("Status=READY"),
        ]
        client = BlastClient()
        await client.poll_until_complete("rid-1")
        assert mock_get.call_count == 3

    @pytest.mark.asyncio
    @patch("src.backend.blast_client.httpx.AsyncClient.get")
    async def test_raises_on_terminal_failure_status(self, mock_get):
        mock_get.return_value = _text_response("Status=FAILED")
        client = BlastClient()
        with pytest.raises(BlastError, match="failed on the server"):
            await client.poll_until_complete("rid-1")

    @pytest.mark.asyncio
    @patch("src.backend.blast_client.asyncio.sleep", new_callable=AsyncMock)
    @patch("src.backend.blast_client.httpx.AsyncClient.get")
    async def test_times_out(self, mock_get, mock_sleep):
        mock_get.return_value = _text_response("Status=WAITING")
        client = BlastClient()
        client.max_poll_attempts = 3
        with pytest.raises(BlastError, match="did not complete"):
            await client.poll_until_complete("rid-1")
        assert mock_get.call_count == 3

    @pytest.mark.asyncio
    @patch("src.backend.blast_client.httpx.AsyncClient.get")
    async def test_wraps_http_errors(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("no route")
        client = BlastClient()
        with pytest.raises(BlastError, match="polling failed"):
            await client.poll_until_complete("rid-1")


class TestFetchHits:
    @pytest.mark.asyncio
    @patch("src.backend.blast_client.httpx.AsyncClient.get")
    async def test_returns_parsed_hits(self, mock_get):
        mock_get.return_value = _text_response(_REAL_LOOKING_XML)
        client = BlastClient()
        hits = await client.fetch_hits("rid-1")
        assert len(hits) == 2
        assert hits[0]["accession"] == "NP_000509"

    @pytest.mark.asyncio
    @patch("src.backend.blast_client.httpx.AsyncClient.get")
    async def test_wraps_http_errors(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("no route")
        client = BlastClient()
        with pytest.raises(BlastError, match="result fetch failed"):
            await client.fetch_hits("rid-1")


class TestFindHomologsAndScoreConservationEndToEnd:
    @pytest.mark.asyncio
    @patch("src.backend.blast_client.httpx.AsyncClient.get")
    @patch("src.backend.blast_client.httpx.AsyncClient.post")
    async def test_submits_polls_fetches_and_scores(self, mock_post, mock_get):
        mock_post.return_value = _text_response("RID = rid-1\nRTOE = 0")
        mock_get.side_effect = [
            _text_response("Status=READY"),
            _text_response(_REAL_LOOKING_XML),
        ]

        client = BlastClient()
        result = await client.find_homologs_and_score_conservation("MVHLTPEEK")

        assert result["rid"] == "rid-1"
        assert result["num_hits"] == 2
        assert len(result["conservation_profile"]) == 9
        assert result["conservation_profile"][0]["conservation"] is not None
