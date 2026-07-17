from unittest.mock import patch, AsyncMock, MagicMock

import httpx
import pytest

from src.backend.ddmut_client import DDMutClient, DDMutError


@pytest.fixture(autouse=True)
def fast_rate_limiter():
    """The real rate limiter enforces a 1s gap between requests, which
    would make every test slow. Zero it out for the duration of these
    tests."""
    original = DDMutClient._rate_limiter._min_interval
    DDMutClient._rate_limiter._min_interval = 0
    DDMutClient._rate_limiter._last_request_at = 0.0
    yield
    DDMutClient._rate_limiter._min_interval = original


def _json_response(json_data, status_code=200):
    response = AsyncMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=json_data)
    response.text = str(json_data)
    return response


class TestSubmitMutation:
    @pytest.mark.asyncio
    @patch("src.backend.ddmut_client.httpx.AsyncClient.post")
    async def test_returns_job_id_from_real_looking_response(self, mock_post):
        mock_post.return_value = _json_response({"job_id": "17843137121455343"})

        client = DDMutClient()
        job_id = await client.submit_mutation("PDB TEXT", "A", "K6A")

        assert job_id == "17843137121455343"
        mock_post.assert_called_once()
        # Submitted as a real file upload, not an accession - works for
        # every structure source this app has, not just real PDB entries.
        _, kwargs = mock_post.call_args
        assert "pdb_file" in kwargs["files"]
        assert kwargs["data"] == {"chain": "A", "mutation": "K6A"}

    @pytest.mark.asyncio
    @patch("src.backend.ddmut_client.httpx.AsyncClient.post")
    async def test_raises_when_no_job_id_returned(self, mock_post):
        mock_post.return_value = _json_response({"error": "bad request"})

        client = DDMutClient()
        with pytest.raises(DDMutError, match="did not return a job_id"):
            await client.submit_mutation("PDB TEXT", "A", "K6A")

    @pytest.mark.asyncio
    @patch("src.backend.ddmut_client.httpx.AsyncClient.post")
    async def test_wraps_http_errors(self, mock_post):
        mock_post.side_effect = httpx.ConnectError("no route")

        client = DDMutClient()
        with pytest.raises(DDMutError, match="submission failed"):
            await client.submit_mutation("PDB TEXT", "A", "K6A")


class TestPollUntilComplete:
    @pytest.mark.asyncio
    @patch("src.backend.ddmut_client.httpx.AsyncClient.request")
    async def test_returns_the_real_completed_payload(self, mock_request):
        mock_request.return_value = _json_response(
            {
                "job_id": "job-1",
                "status": "DONE",
                "prediction": 0.22,
                "chain": "A",
                "position": "6",
                "wild-type": "LYS",
                "mutant": "ALA",
                "results_page": "https://biosig.lab.uq.edu.au/ddmut/results_prediction/job-1",
            }
        )

        client = DDMutClient()
        result = await client.poll_until_complete("job-1")

        assert result["prediction"] == 0.22
        mock_request.assert_called_once()
        # Polling is a GET carrying job_id as form data, not a query string
        # (verified live - a query-string GET returns a server error).
        args, kwargs = mock_request.call_args
        assert args[0] == "GET"
        assert kwargs["data"] == {"job_id": "job-1"}

    @pytest.mark.asyncio
    @patch("src.backend.ddmut_client.asyncio.sleep", new_callable=AsyncMock)
    @patch("src.backend.ddmut_client.httpx.AsyncClient.request")
    async def test_keeps_polling_while_running(self, mock_request, mock_sleep):
        mock_request.side_effect = [
            _json_response({"job_id": "job-1", "status": "RUNNING"}),
            _json_response({"job_id": "job-1", "status": "RUNNING"}),
            _json_response({"job_id": "job-1", "status": "DONE", "prediction": -1.67}),
        ]

        client = DDMutClient()
        result = await client.poll_until_complete("job-1")

        assert result["prediction"] == -1.67
        assert mock_request.call_count == 3

    @pytest.mark.asyncio
    @patch("src.backend.ddmut_client.httpx.AsyncClient.request")
    async def test_raises_on_terminal_failure_status(self, mock_request):
        mock_request.return_value = _json_response(
            {"job_id": "job-1", "status": "ERROR"}
        )

        client = DDMutClient()
        with pytest.raises(DDMutError, match="failed on the server"):
            await client.poll_until_complete("job-1")

    @pytest.mark.asyncio
    @patch("src.backend.ddmut_client.asyncio.sleep", new_callable=AsyncMock)
    @patch("src.backend.ddmut_client.httpx.AsyncClient.request")
    async def test_times_out(self, mock_request, mock_sleep):
        mock_request.return_value = _json_response(
            {"job_id": "job-1", "status": "RUNNING"}
        )

        client = DDMutClient()
        client.max_poll_attempts = 3
        with pytest.raises(DDMutError, match="did not complete"):
            await client.poll_until_complete("job-1")
        assert mock_request.call_count == 3

    @pytest.mark.asyncio
    @patch("src.backend.ddmut_client.httpx.AsyncClient.request")
    async def test_wraps_http_errors(self, mock_request):
        mock_request.side_effect = httpx.ConnectError("no route")

        client = DDMutClient()
        with pytest.raises(DDMutError, match="polling failed"):
            await client.poll_until_complete("job-1")


class TestPredictStability:
    @pytest.mark.asyncio
    @patch("src.backend.ddmut_client.httpx.AsyncClient.request")
    @patch("src.backend.ddmut_client.httpx.AsyncClient.post")
    async def test_submits_then_polls_and_returns_the_final_result(
        self, mock_post, mock_request
    ):
        mock_post.return_value = _json_response({"job_id": "job-1"})
        mock_request.return_value = _json_response(
            {"job_id": "job-1", "status": "DONE", "prediction": 0.22}
        )

        client = DDMutClient()
        result = await client.predict_stability("PDB TEXT", "A", "K6A")

        assert result["prediction"] == 0.22
        mock_post.assert_called_once()
        mock_request.assert_called_once()
