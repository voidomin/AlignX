from unittest.mock import patch, AsyncMock, MagicMock

import httpx
import pytest

from src.backend.interproscan_client import InterProScanClient, InterProScanError


@pytest.fixture(autouse=True)
def fast_rate_limiter():
    """The real rate limiter enforces a 3s gap between requests, which would
    make every test slow. Zero it out for the duration of these tests."""
    original = InterProScanClient._rate_limiter._min_interval
    InterProScanClient._rate_limiter._min_interval = 0
    InterProScanClient._rate_limiter._last_request_at = 0.0
    yield
    InterProScanClient._rate_limiter._min_interval = original


def _text_response(text):
    response = AsyncMock()
    response.raise_for_status = MagicMock()
    response.text = text
    return response


def _json_response(json_data):
    response = AsyncMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=json_data)
    return response


class TestSubmitSequence:
    @pytest.mark.asyncio
    @patch("src.backend.interproscan_client.httpx.AsyncClient.post")
    async def test_returns_job_id_from_plain_text_response(self, mock_post):
        mock_post.return_value = _text_response(
            "iprscan5-R20260721-061714-0451-81111570-p1m"
        )

        client = InterProScanClient()
        job_id = await client.submit_sequence("MVHLTPEEKSAVTALWGKVNV")

        assert job_id == "iprscan5-R20260721-061714-0451-81111570-p1m"
        _, kwargs = mock_post.call_args
        assert kwargs["data"]["appl"] == "PfamA,PrositeProfiles"
        assert kwargs["data"]["goterms"] == "true"

    @pytest.mark.asyncio
    @patch("src.backend.interproscan_client.httpx.AsyncClient.post")
    async def test_raises_when_no_job_id_returned(self, mock_post):
        mock_post.return_value = _text_response("   ")

        client = InterProScanClient()
        with pytest.raises(InterProScanError, match="did not return a job ID"):
            await client.submit_sequence("MVHLTPEEKSAVTALWGKVNV")

    @pytest.mark.asyncio
    @patch("src.backend.interproscan_client.httpx.AsyncClient.post")
    async def test_wraps_http_errors(self, mock_post):
        mock_post.side_effect = httpx.ConnectError("no route")

        client = InterProScanClient()
        with pytest.raises(InterProScanError, match="submission failed"):
            await client.submit_sequence("MVHLTPEEKSAVTALWGKVNV")


class TestPollUntilComplete:
    @pytest.mark.asyncio
    @patch("src.backend.interproscan_client.httpx.AsyncClient.get")
    async def test_returns_on_finished(self, mock_get):
        mock_get.return_value = _text_response("FINISHED")

        client = InterProScanClient()
        await client.poll_until_complete("job-1")
        mock_get.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.backend.interproscan_client.asyncio.sleep", new_callable=AsyncMock)
    @patch("src.backend.interproscan_client.httpx.AsyncClient.get")
    async def test_keeps_polling_while_in_progress(self, mock_get, mock_sleep):
        mock_get.side_effect = [
            _text_response("QUEUED"),
            _text_response("RUNNING"),
            _text_response("FINISHED"),
        ]

        client = InterProScanClient()
        await client.poll_until_complete("job-1")
        assert mock_get.call_count == 3

    @pytest.mark.asyncio
    @patch("src.backend.interproscan_client.httpx.AsyncClient.get")
    async def test_raises_on_terminal_failure_status(self, mock_get):
        mock_get.return_value = _text_response("ERROR")

        client = InterProScanClient()
        with pytest.raises(InterProScanError, match="failed on the server"):
            await client.poll_until_complete("job-1")

    @pytest.mark.asyncio
    @patch("src.backend.interproscan_client.asyncio.sleep", new_callable=AsyncMock)
    @patch("src.backend.interproscan_client.httpx.AsyncClient.get")
    async def test_times_out(self, mock_get, mock_sleep):
        mock_get.return_value = _text_response("RUNNING")

        client = InterProScanClient()
        client.max_poll_attempts = 3
        with pytest.raises(InterProScanError, match="did not complete"):
            await client.poll_until_complete("job-1")
        assert mock_get.call_count == 3

    @pytest.mark.asyncio
    @patch("src.backend.interproscan_client.httpx.AsyncClient.get")
    async def test_wraps_http_errors(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("no route")

        client = InterProScanClient()
        with pytest.raises(InterProScanError, match="polling failed"):
            await client.poll_until_complete("job-1")


class TestFetchResult:
    @pytest.mark.asyncio
    @patch("src.backend.interproscan_client.httpx.AsyncClient.get")
    async def test_returns_real_result_json(self, mock_get):
        mock_get.return_value = _json_response({"results": [{"matches": []}]})

        client = InterProScanClient()
        result = await client.fetch_result("job-1")

        assert result == {"results": [{"matches": []}]}

    @pytest.mark.asyncio
    @patch("src.backend.interproscan_client.httpx.AsyncClient.get")
    async def test_wraps_http_errors(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("no route")

        client = InterProScanClient()
        with pytest.raises(InterProScanError, match="result fetch failed"):
            await client.fetch_result("job-1")


class TestAnnotateEndToEnd:
    @pytest.mark.asyncio
    @patch("src.backend.interproscan_client.httpx.AsyncClient.get")
    @patch("src.backend.interproscan_client.httpx.AsyncClient.post")
    async def test_submits_polls_and_fetches(self, mock_post, mock_get):
        mock_post.return_value = _text_response("job-1")
        mock_get.side_effect = [
            _text_response("FINISHED"),
            _json_response({"results": [{"matches": []}]}),
        ]

        client = InterProScanClient()
        result = await client.annotate("MVHLTPEEKSAVTALWGKVNV")

        assert result == {"results": [{"matches": []}]}


class TestParseDomainsAndGoTerms:
    def test_parses_a_real_looking_globin_result(self):
        result = {
            "results": [
                {
                    "matches": [
                        {
                            "signature": {
                                "entry": {
                                    "accession": "IPR000971",
                                    "name": "Globin",
                                    "type": "DOMAIN",
                                    "goXRefs": [
                                        {
                                            "id": "GO:0020037",
                                            "name": "heme binding",
                                            "category": "MOLECULAR_FUNCTION",
                                        }
                                    ],
                                }
                            },
                            "locations": [{"start": 27, "end": 142}],
                        }
                    ]
                }
            ]
        }

        domains, go_terms = InterProScanClient.parse_domains_and_go_terms(result)

        assert domains == [
            {
                "accession": "IPR000971",
                "name": "Globin",
                "type": "DOMAIN",
                "locations": [{"start": 27, "end": 142}],
            }
        ]
        assert go_terms == [
            {"id": "GO:0020037", "name": "heme binding", "aspect": "MOLECULAR_FUNCTION"}
        ]

    def test_deduplicates_go_terms_by_id_across_matches(self):
        result = {
            "results": [
                {
                    "matches": [
                        {
                            "signature": {
                                "entry": {
                                    "accession": "IPR000971",
                                    "name": "Globin",
                                    "goXRefs": [
                                        {"id": "GO:0020037", "name": "heme binding"}
                                    ],
                                }
                            },
                            "locations": [],
                        },
                        {
                            "signature": {
                                "entry": {
                                    "accession": "PS01033",
                                    "name": "Globin",
                                    "goXRefs": [
                                        {"id": "GO:0020037", "name": "heme binding"}
                                    ],
                                }
                            },
                            "locations": [],
                        },
                    ]
                }
            ]
        }

        domains, go_terms = InterProScanClient.parse_domains_and_go_terms(result)

        assert len(domains) == 2
        assert len(go_terms) == 1

    def test_returns_empty_lists_for_no_matches(self):
        domains, go_terms = InterProScanClient.parse_domains_and_go_terms(
            {"results": [{"matches": []}]}
        )
        assert domains == []
        assert go_terms == []

    def test_skips_matches_with_no_entry_accession(self):
        # Some signatures (e.g. unintegrated Pfam hits) have no InterPro
        # entry cross-reference at all - not every raw signature match is
        # a real, citable domain call.
        result = {
            "results": [
                {
                    "matches": [
                        {"signature": {"entry": {}}, "locations": []},
                    ]
                }
            ]
        }
        domains, go_terms = InterProScanClient.parse_domains_and_go_terms(result)
        assert domains == []
        assert go_terms == []
