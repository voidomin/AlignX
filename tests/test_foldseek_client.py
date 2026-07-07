import asyncio
import threading
from unittest.mock import patch, AsyncMock, MagicMock

import pytest

from src.backend.foldseek_client import FoldseekClient, FoldseekError


@pytest.fixture(autouse=True)
def fast_rate_limiter():
    """The real rate limiter enforces a 10s gap between requests, which would
    make every test slow. Zero it out for the duration of these tests."""
    original = FoldseekClient._rate_limiter._min_interval
    FoldseekClient._rate_limiter._min_interval = 0
    FoldseekClient._rate_limiter._last_request_at = 0.0
    yield
    FoldseekClient._rate_limiter._min_interval = original


class TestFoldseekClient:

    def test_validate_databases_accepts_allowed(self):
        assert FoldseekClient.validate_databases(["pdb100", "afdb50"]) == [
            "pdb100",
            "afdb50",
        ]

    def test_validate_databases_rejects_unknown(self):
        with pytest.raises(FoldseekError, match="Unsupported"):
            FoldseekClient.validate_databases(["not-a-real-db"])

    def test_parse_hits_from_results_wrapper(self):
        raw = {
            "results": [
                {"alignments": [[{"target": "1ABC"}, {"target": "2XYZ"}]]},
            ]
        }
        hits = FoldseekClient.parse_hits(raw)
        assert [h["target"] for h in hits] == ["1ABC", "2XYZ"]

    def test_parse_hits_from_flat_alignments(self):
        raw = {"alignments": [{"target": "3DEF"}]}
        assert [h["target"] for h in FoldseekClient.parse_hits(raw)] == ["3DEF"]

    def test_parse_hits_handles_empty(self):
        assert FoldseekClient.parse_hits({}) == []

    @pytest.mark.asyncio
    @patch("src.backend.foldseek_client.httpx.AsyncClient.post")
    async def test_submit_search_returns_ticket_id(self, mock_post, tmp_path):
        structure = tmp_path / "query.pdb"
        structure.write_text("ATOM\n")

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"id": "abc123"})
        mock_post.return_value = mock_response

        client = FoldseekClient()
        ticket_id = await client.submit_search(structure, databases=["pdb100"])

        assert ticket_id == "abc123"
        mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_submit_search_rejects_bad_database(self, tmp_path):
        structure = tmp_path / "query.pdb"
        structure.write_text("ATOM\n")

        client = FoldseekClient()
        with pytest.raises(FoldseekError, match="Unsupported"):
            await client.submit_search(structure, databases=["bogus"])

    @pytest.mark.asyncio
    @patch("src.backend.foldseek_client.httpx.AsyncClient.post")
    async def test_submit_search_raises_when_no_ticket_id(self, mock_post, tmp_path):
        structure = tmp_path / "query.pdb"
        structure.write_text("ATOM\n")

        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"status": "error, no id"})
        mock_post.return_value = mock_response

        client = FoldseekClient()
        with pytest.raises(FoldseekError, match="did not return a ticket"):
            await client.submit_search(structure, databases=["pdb100"])

    @pytest.mark.asyncio
    @patch("src.backend.foldseek_client.httpx.AsyncClient.get")
    async def test_poll_until_complete_returns_on_complete(self, mock_get):
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"status": "COMPLETE"})
        mock_get.return_value = mock_response

        client = FoldseekClient()
        await client.poll_until_complete("ticket-1")
        mock_get.assert_called_once()

    @pytest.mark.asyncio
    @patch("src.backend.foldseek_client.httpx.AsyncClient.get")
    async def test_poll_until_complete_raises_on_server_error(self, mock_get):
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"status": "ERROR"})
        mock_get.return_value = mock_response

        client = FoldseekClient()
        with pytest.raises(FoldseekError, match="failed on the server"):
            await client.poll_until_complete("ticket-1")

    @pytest.mark.asyncio
    @patch("src.backend.foldseek_client.asyncio.sleep", new_callable=AsyncMock)
    @patch("src.backend.foldseek_client.httpx.AsyncClient.get")
    async def test_poll_until_complete_times_out(self, mock_get, mock_sleep):
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={"status": "RUNNING"})
        mock_get.return_value = mock_response

        client = FoldseekClient()
        client.max_poll_attempts = 3
        with pytest.raises(FoldseekError, match="did not complete"):
            await client.poll_until_complete("ticket-1")
        assert mock_get.call_count == 3

    @pytest.mark.asyncio
    @patch("src.backend.foldseek_client.httpx.AsyncClient.get")
    async def test_fetch_results_returns_json(self, mock_get):
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(
            return_value={"alignments": [{"target": "1ABC"}]}
        )
        mock_get.return_value = mock_response

        client = FoldseekClient()
        result = await client.fetch_results("ticket-1")
        assert result == {"alignments": [{"target": "1ABC"}]}


class TestRateLimiterCrossThreadSafety:
    """Regression test: each Discover job runs its Foldseek calls inside its
    own asyncio.run() on a dedicated worker thread, so concurrent jobs hit
    the shared, class-level rate limiter from different event loops. An
    asyncio.Lock-based limiter hung one of three concurrent callers forever
    in direct testing (its waiter Futures are bound to the loop that
    created them, not safe to release from a different loop) - this must
    stay a threading.Lock, not regress back to asyncio.Lock."""

    def test_concurrent_waiters_from_different_threads_all_complete(self):
        limiter = FoldseekClient._rate_limiter
        original_interval = limiter._min_interval
        limiter._min_interval = 0.2
        limiter._last_request_at = 0.0

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

        limiter._min_interval = original_interval

        assert not any(t.is_alive() for t in threads), "a waiter thread hung"
        assert errors == []
        assert len(completed) == 5
