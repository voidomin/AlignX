import json
from unittest.mock import patch, AsyncMock, MagicMock

import httpx
import pytest

from src.backend.prankweb_client import PrankWebClient, PrankWebError


@pytest.fixture(autouse=True)
def fast_rate_limiter():
    """The real rate limiter enforces a 1s gap between requests, which
    would make every test slow. Zero it out for the duration of these
    tests."""
    original = PrankWebClient._rate_limiter._min_interval
    PrankWebClient._rate_limiter._min_interval = 0
    PrankWebClient._rate_limiter._last_request_at = 0.0
    yield
    PrankWebClient._rate_limiter._min_interval = original


def _json_response(json_data, status_code=200):
    response = AsyncMock()
    response.raise_for_status = MagicMock()
    response.json = MagicMock(return_value=json_data)
    response.text = str(json_data)
    return response


class TestSubmitStructure:
    @pytest.mark.asyncio
    @patch("src.backend.prankweb_client.httpx.AsyncClient.post")
    async def test_returns_job_id_from_real_looking_response(self, mock_post):
        mock_post.return_value = _json_response(
            {
                "id": "2026-07-20-16-33-59-D852F1B5",
                "database": "v3-user-upload",
                "status": "queued",
            }
        )

        client = PrankWebClient()
        job_id = await client.submit_structure("PDB TEXT")

        assert job_id == "2026-07-20-16-33-59-D852F1B5"
        mock_post.assert_called_once()
        # Submitted as a real file upload (two multipart fields), not a
        # PDB accession - works for every structure source this app has.
        _, kwargs = mock_post.call_args
        assert "structure" in kwargs["files"]
        assert "configuration" in kwargs["files"]
        config = json.loads(kwargs["files"]["configuration"][1])
        assert config == {
            "structure-sealed": True,
            "chains": [],
            "prediction-model": "default",
        }

    @pytest.mark.asyncio
    @patch("src.backend.prankweb_client.httpx.AsyncClient.post")
    async def test_raises_when_no_id_returned(self, mock_post):
        mock_post.return_value = _json_response({"error": "bad request"})

        client = PrankWebClient()
        with pytest.raises(PrankWebError, match="did not return an id"):
            await client.submit_structure("PDB TEXT")

    @pytest.mark.asyncio
    @patch("src.backend.prankweb_client.httpx.AsyncClient.post")
    async def test_wraps_http_errors(self, mock_post):
        mock_post.side_effect = httpx.ConnectError("no route")

        client = PrankWebClient()
        with pytest.raises(PrankWebError, match="submission failed"):
            await client.submit_structure("PDB TEXT")

    @pytest.mark.asyncio
    @patch("src.backend.prankweb_client.httpx.AsyncClient.post")
    async def test_recovers_from_a_single_transient_connection_error(self, mock_post):
        # Confirmed live: a real submission attempt occasionally drops the
        # connection with no other symptom - a one-shot retry recovers it.
        mock_post.side_effect = [
            httpx.ConnectError("no route"),
            _json_response({"id": "job-1"}),
        ]

        client = PrankWebClient()
        job_id = await client.submit_structure("PDB TEXT")

        assert job_id == "job-1"
        assert mock_post.call_count == 2


class TestPollUntilComplete:
    @pytest.mark.asyncio
    @patch("src.backend.prankweb_client.httpx.AsyncClient.get")
    async def test_returns_the_real_completed_payload(self, mock_get):
        mock_get.side_effect = [
            _json_response({"id": "job-1", "status": "successful"}),
            _json_response({"pockets": [{"name": "pocket1", "rank": "1"}]}),
        ]

        client = PrankWebClient()
        result = await client.poll_until_complete("job-1")

        assert result["pockets"][0]["name"] == "pocket1"
        assert mock_get.call_count == 2
        # Status and result are two separate URLs on this service, unlike
        # DDMut's single shared endpoint.
        status_url = mock_get.call_args_list[0].args[0]
        result_url = mock_get.call_args_list[1].args[0]
        assert status_url.endswith("/job-1")
        assert result_url.endswith("/job-1/public/prediction.json")

    @pytest.mark.asyncio
    @patch("src.backend.prankweb_client.asyncio.sleep", new_callable=AsyncMock)
    @patch("src.backend.prankweb_client.httpx.AsyncClient.get")
    async def test_keeps_polling_while_queued(self, mock_get, mock_sleep):
        mock_get.side_effect = [
            _json_response({"id": "job-1", "status": "queued"}),
            _json_response({"id": "job-1", "status": "queued"}),
            _json_response({"id": "job-1", "status": "successful"}),
            _json_response({"pockets": []}),
        ]

        client = PrankWebClient()
        result = await client.poll_until_complete("job-1")

        assert result["pockets"] == []
        assert mock_get.call_count == 4

    @pytest.mark.asyncio
    @patch("src.backend.prankweb_client.httpx.AsyncClient.get")
    async def test_raises_on_terminal_failure_status(self, mock_get):
        mock_get.return_value = _json_response({"id": "job-1", "status": "failed"})

        client = PrankWebClient()
        with pytest.raises(PrankWebError, match="failed on the server"):
            await client.poll_until_complete("job-1")

    @pytest.mark.asyncio
    @patch("src.backend.prankweb_client.asyncio.sleep", new_callable=AsyncMock)
    @patch("src.backend.prankweb_client.httpx.AsyncClient.get")
    async def test_times_out(self, mock_get, mock_sleep):
        mock_get.return_value = _json_response({"id": "job-1", "status": "queued"})

        client = PrankWebClient()
        client.max_poll_attempts = 3
        with pytest.raises(PrankWebError, match="did not complete"):
            await client.poll_until_complete("job-1")
        assert mock_get.call_count == 3

    @pytest.mark.asyncio
    @patch("src.backend.prankweb_client.asyncio.sleep", new_callable=AsyncMock)
    @patch("src.backend.prankweb_client.httpx.AsyncClient.get")
    async def test_recovers_from_a_single_transient_connection_error(
        self, mock_get, mock_sleep
    ):
        # Confirmed live: a real poll loop against PrankWeb's server can
        # drop one connection attempt mid-sequence with no other symptom -
        # this must not fail the whole job over a single blip.
        mock_get.side_effect = [
            httpx.ConnectError("no route"),
            _json_response({"id": "job-1", "status": "successful"}),
            _json_response({"pockets": []}),
        ]

        client = PrankWebClient()
        result = await client.poll_until_complete("job-1")

        assert result["pockets"] == []
        assert mock_get.call_count == 3

    @pytest.mark.asyncio
    @patch("src.backend.prankweb_client.asyncio.sleep", new_callable=AsyncMock)
    @patch("src.backend.prankweb_client.httpx.AsyncClient.get")
    async def test_gives_up_after_too_many_consecutive_transport_errors(
        self, mock_get, mock_sleep
    ):
        mock_get.side_effect = httpx.ConnectError("no route")

        client = PrankWebClient()
        with pytest.raises(PrankWebError, match="polling failed"):
            await client.poll_until_complete("job-1")

    @pytest.mark.asyncio
    @patch("src.backend.prankweb_client.httpx.AsyncClient.get")
    async def test_wraps_a_non_transient_http_error_immediately_without_retrying(
        self, mock_get
    ):
        response = _json_response({"id": "job-1"})
        response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "server error", request=MagicMock(), response=MagicMock()
            )
        )
        mock_get.return_value = response

        client = PrankWebClient()
        with pytest.raises(PrankWebError, match="polling failed"):
            await client.poll_until_complete("job-1")
        mock_get.assert_called_once()


class TestDetectPockets:
    @pytest.mark.asyncio
    @patch("src.backend.prankweb_client.httpx.AsyncClient.get")
    @patch("src.backend.prankweb_client.httpx.AsyncClient.post")
    async def test_submits_then_polls_and_returns_the_final_result(
        self, mock_post, mock_get
    ):
        mock_post.return_value = _json_response({"id": "job-1", "status": "queued"})
        mock_get.side_effect = [
            _json_response({"id": "job-1", "status": "successful"}),
            _json_response({"pockets": [{"name": "pocket1"}]}),
        ]

        client = PrankWebClient()
        result = await client.detect_pockets("PDB TEXT")

        assert result["pockets"][0]["name"] == "pocket1"
        mock_post.assert_called_once()
        assert mock_get.call_count == 2
