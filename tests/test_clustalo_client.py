from unittest.mock import patch, AsyncMock, MagicMock

import httpx
import pytest

from src.backend.clustalo_client import ClustalOmegaClient, ClustalOmegaError


@pytest.fixture(autouse=True)
def fast_rate_limiter():
    """The real rate limiter enforces a 3s gap between requests, which would
    make every test slow. Zero it out for the duration of these tests."""
    original = ClustalOmegaClient._rate_limiter._min_interval
    ClustalOmegaClient._rate_limiter._min_interval = 0
    ClustalOmegaClient._rate_limiter._last_request_at = 0.0
    yield
    ClustalOmegaClient._rate_limiter._min_interval = original


class TestToFasta:
    def test_builds_real_fasta_text(self):
        result = ClustalOmegaClient._to_fasta({"seq1": "MVHL", "seq2": "MVLS"})
        assert result == ">seq1\nMVHL\n>seq2\nMVLS"


class TestSubmitAlignment:
    @pytest.mark.asyncio
    async def test_rejects_fewer_than_two_sequences(self):
        client = ClustalOmegaClient()
        with pytest.raises(ClustalOmegaError, match="At least 2 sequences"):
            await client.submit_alignment({"seq1": "MVHL"})

    @pytest.mark.asyncio
    @patch("src.backend.clustalo_client.httpx.AsyncClient.post")
    async def test_returns_job_id_from_plain_text_response(self, mock_post):
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.text = "clustalo-R20260715-204957-0411-336085-p1m"
        mock_post.return_value = mock_response

        client = ClustalOmegaClient()
        job_id = await client.submit_alignment({"seq1": "MVHL", "seq2": "MVLS"})

        assert job_id == "clustalo-R20260715-204957-0411-336085-p1m"
        mock_post.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.backend.clustalo_client.httpx.AsyncClient.post")
    async def test_raises_when_no_job_id_returned(self, mock_post):
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.text = "   "
        mock_post.return_value = mock_response

        client = ClustalOmegaClient()
        with pytest.raises(ClustalOmegaError, match="did not return a job ID"):
            await client.submit_alignment({"seq1": "MVHL", "seq2": "MVLS"})

    @pytest.mark.asyncio
    @patch("src.backend.clustalo_client.httpx.AsyncClient.post")
    async def test_wraps_http_errors(self, mock_post):
        mock_post.side_effect = httpx.ConnectError("no route")

        client = ClustalOmegaClient()
        with pytest.raises(ClustalOmegaError, match="submission failed"):
            await client.submit_alignment({"seq1": "MVHL", "seq2": "MVLS"})


class TestPollUntilComplete:
    @pytest.mark.asyncio
    @patch("src.backend.clustalo_client.httpx.AsyncClient.get")
    async def test_returns_on_finished(self, mock_get):
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.text = "FINISHED"
        mock_get.return_value = mock_response

        client = ClustalOmegaClient()
        await client.poll_until_complete("job-1")
        mock_get.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.backend.clustalo_client.asyncio.sleep", new_callable=AsyncMock)
    @patch("src.backend.clustalo_client.httpx.AsyncClient.get")
    async def test_keeps_polling_while_in_progress(self, mock_get, mock_sleep):
        responses = [
            _text_response("QUEUED"),
            _text_response("RUNNING"),
            _text_response("FINISHED"),
        ]
        mock_get.side_effect = responses

        client = ClustalOmegaClient()
        await client.poll_until_complete("job-1")
        assert mock_get.call_count == 3

    @pytest.mark.asyncio
    @patch("src.backend.clustalo_client.httpx.AsyncClient.get")
    async def test_raises_on_terminal_failure_status(self, mock_get):
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.text = "ERROR"
        mock_get.return_value = mock_response

        client = ClustalOmegaClient()
        with pytest.raises(ClustalOmegaError, match="failed on the server"):
            await client.poll_until_complete("job-1")

    @pytest.mark.asyncio
    @patch("src.backend.clustalo_client.asyncio.sleep", new_callable=AsyncMock)
    @patch("src.backend.clustalo_client.httpx.AsyncClient.get")
    async def test_times_out(self, mock_get, mock_sleep):
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.text = "RUNNING"
        mock_get.return_value = mock_response

        client = ClustalOmegaClient()
        client.max_poll_attempts = 3
        with pytest.raises(ClustalOmegaError, match="did not complete"):
            await client.poll_until_complete("job-1")
        assert mock_get.call_count == 3

    @pytest.mark.asyncio
    @patch("src.backend.clustalo_client.httpx.AsyncClient.get")
    async def test_wraps_http_errors(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("no route")

        client = ClustalOmegaClient()
        with pytest.raises(ClustalOmegaError, match="polling failed"):
            await client.poll_until_complete("job-1")


def _text_response(text):
    response = AsyncMock()
    response.raise_for_status = MagicMock()
    response.text = text
    return response


class TestFetchAlignment:
    @pytest.mark.asyncio
    @patch("src.backend.clustalo_client.httpx.AsyncClient.get")
    async def test_returns_real_aligned_fasta_text(self, mock_get):
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.text = ">seq1\nMV--HL\n>seq2\n-MVLSH"
        mock_get.return_value = mock_response

        client = ClustalOmegaClient()
        result = await client.fetch_alignment("job-1")

        assert result == ">seq1\nMV--HL\n>seq2\n-MVLSH"

    @pytest.mark.asyncio
    @patch("src.backend.clustalo_client.httpx.AsyncClient.get")
    async def test_wraps_http_errors(self, mock_get):
        mock_get.side_effect = httpx.ConnectError("no route")

        client = ClustalOmegaClient()
        with pytest.raises(ClustalOmegaError, match="result fetch failed"):
            await client.fetch_alignment("job-1")


class TestAlignEndToEnd:
    @pytest.mark.asyncio
    @patch("src.backend.clustalo_client.httpx.AsyncClient.get")
    @patch("src.backend.clustalo_client.httpx.AsyncClient.post")
    async def test_submits_polls_and_fetches(self, mock_post, mock_get):
        mock_post.return_value = _text_response("job-1")
        mock_get.side_effect = [
            _text_response("FINISHED"),
            _text_response(">a\nMV\n>b\nML"),
        ]

        client = ClustalOmegaClient()
        result = await client.align({"a": "MV", "b": "ML"})

        assert result == ">a\nMV\n>b\nML"
